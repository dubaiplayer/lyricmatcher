from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
import numpy as np
import pandas as pd
import re
import os
import json
import hashlib
import threading
from rapidfuzz import process, fuzz
import lyricsgenius

# Avoid tokenizer fork warnings on some platforms.
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

token = "e6l3UT59vCDVuu4ZYardyaXRDolUtSr636-TAH1CHU5Tw0yt3lPnRjnyKoaQ2hb9"
genius = lyricsgenius.Genius(token)
genius.verbose = False
genius.remove_section_headers = True
genius.skip_non_songs = True

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
DATASET_PATH = "./spotify_millsongdata.csv"
TOP_K = 5
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(_BACKEND_DIR, "recommender_cache")
EMBEDDINGS_CACHE_PATH = os.path.join(CACHE_DIR, "lyrics_embeddings.npy")
METADATA_CACHE_PATH = os.path.join(CACHE_DIR, "lyrics_cache_meta.json")
TFIDF_WORD_CACHE_PATH = os.path.join(CACHE_DIR, "tfidf_word.npz")
TFIDF_CHAR_CACHE_PATH = os.path.join(CACHE_DIR, "tfidf_char.npz")
TFIDF_WORD_VECTORIZER_PATH = os.path.join(CACHE_DIR, "tfidf_word_vectorizer.joblib")
TFIDF_CHAR_VECTORIZER_PATH = os.path.join(CACHE_DIR, "tfidf_char_vectorizer.joblib")
_EMBEDDING_MODEL = None
_MAX_INCREMENTAL_ROWS = 64
# Hugging Face Hub accepts HF_TOKEN or HUGGING_FACE_HUB_TOKEN (IDE terminals may not see new User env vars until restart).
HF_TOKEN = (os.getenv("HF_TOKEN") or os.getenv("HUGGING_FACE_HUB_TOKEN") or "").strip()
if HF_TOKEN:
    os.environ["HF_TOKEN"] = HF_TOKEN
    os.environ["HUGGING_FACE_HUB_TOKEN"] = HF_TOKEN

# MiniLM uses ~256 subword tokens; long strings only slow tokenization on CPU.
_EMBED_TEXT_CHAR_CAP = 2048
_ENCODE_MP_MIN_TEXTS = 2000
_PREPARED_COLUMNS = frozenset(
    {"artistCleaned", "songCleaned", "textCleaned", "combinedMeta", "featureText"}
)
_dataset_lock = threading.Lock()
_dataset_cache: dict = {"df": None, "mtime": None}


def clean(text):
    text = str(text).lower()
    text = re.sub(r"\(.*?\)|\[.*?\]", "", text)
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_lyrics(text):
    text = str(text)
    text = re.sub(r"^\s*.*?lyrics\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\d*embed\s*$", "", text, flags=re.IGNORECASE)
    return clean(text)


def _normalize_scores(scores):
    scores = np.asarray(scores, dtype=float)
    s_min = scores.min()
    s_max = scores.max()
    if s_max - s_min < 1e-9:
        return np.zeros_like(scores)
    return (scores - s_min) / (s_max - s_min)


def _get_dataset_signature(df, num_rows=None):
    base = df[["artist", "song", "text"]].fillna("").astype(str)
    if num_rows is not None:
        base = base.iloc[:num_rows]
    # Stable hash for cache invalidation when dataset changes.
    joined = "\n".join(base["artist"] + "||" + base["song"] + "||" + base["text"])
    return hashlib.md5(joined.encode("utf-8")).hexdigest()


def _infer_device():
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
        # Apple Silicon (optional)
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


def _get_encode_batch_size():
    if os.getenv("ENCODE_BATCH_SIZE"):
        return max(8, int(os.getenv("ENCODE_BATCH_SIZE", "128")))
    # Large batches thrash CPU cache; GPU benefits from bigger batches.
    return 512 if _infer_device() == "cuda" else 96


def _get_embedding_model():
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is None:
        try:
            import torch

            torch.set_num_threads(max(1, os.cpu_count() or 4))
            if hasattr(torch, "set_float32_matmul_precision"):
                torch.set_float32_matmul_precision("high")
        except Exception:
            pass
        kwargs = {}
        if HF_TOKEN:
            kwargs["token"] = HF_TOKEN
        _EMBEDDING_MODEL = SentenceTransformer(EMBEDDING_MODEL_NAME, **kwargs)
        _EMBEDDING_MODEL.eval()
        device = _infer_device()
        try:
            _EMBEDDING_MODEL = _EMBEDDING_MODEL.to(device)
        except Exception:
            pass
    return _EMBEDDING_MODEL


def _encode_texts(model, texts, show_progress):
    batch_size = _get_encode_batch_size()
    encode_kwargs = {
        "batch_size": batch_size,
        "normalize_embeddings": True,
        "convert_to_numpy": True,
        "show_progress_bar": show_progress,
    }
    device = _infer_device()
    use_multiprocess = (
        device == "cpu"
        and len(texts) >= _ENCODE_MP_MIN_TEXTS
        and os.getenv("ENCODE_MULTIPROCESS", "1") != "0"
    )
    if use_multiprocess:
        try:
            pool = model.start_multi_process_pool()
            try:
                workers = max(1, (os.cpu_count() or 4) // 2)
                chunk_size = max(1000, len(texts) // workers)
                return model.encode_multi_process(
                    texts,
                    pool,
                    batch_size=batch_size,
                    chunk_size=chunk_size,
                    normalize_embeddings=True,
                    show_progress_bar=show_progress,
                )
            finally:
                model.stop_multi_process_pool(pool)
        except Exception:
            pass

    try:
        import torch
    except ImportError:
        torch = None
    if torch is not None:
        with torch.inference_mode():
            return model.encode(texts, **encode_kwargs)
    return model.encode(texts, **encode_kwargs)


def _text_for_embedding(feature_text: str) -> str:
    """Encoder input cap: model truncates to ~256 tokens; long strings slow tokenization on CPU."""
    if len(feature_text) <= _EMBED_TEXT_CHAR_CAP:
        return feature_text
    return feature_text[:_EMBED_TEXT_CHAR_CAP]


def _read_cache_meta():
    if not os.path.exists(METADATA_CACHE_PATH):
        return None
    try:
        with open(METADATA_CACHE_PATH, "r", encoding="utf-8") as fp:
            return json.load(fp)
    except Exception:
        return None


def _load_cached_embeddings(signature, expected_rows):
    if not os.path.exists(EMBEDDINGS_CACHE_PATH):
        return None
    try:
        meta = _read_cache_meta()
        if meta is None or meta.get("dataset_signature") != signature:
            return None
        embeddings = np.load(EMBEDDINGS_CACHE_PATH)
        if embeddings.shape[0] != expected_rows:
            return None
        return embeddings
    except Exception:
        return None


def _try_incremental_embeddings(df, signature, expected_rows, *, verbose=True):
    """Reuse cache when rows were only appended (e.g. one Genius add), not rewritten."""
    meta = _read_cache_meta()
    if meta is None or not os.path.exists(EMBEDDINGS_CACHE_PATH):
        return None
    cached_rows = int(meta.get("rows", 0))
    if expected_rows <= cached_rows or expected_rows - cached_rows > _MAX_INCREMENTAL_ROWS:
        return None
    try:
        embeddings = np.load(EMBEDDINGS_CACHE_PATH)
        if embeddings.shape[0] != cached_rows:
            return None
        prefix_sig = _get_dataset_signature(df, cached_rows)
        if prefix_sig != meta.get("dataset_signature"):
            return None
        new_texts = [_text_for_embedding(t) for t in df.iloc[cached_rows:]["featureText"].tolist()]
        model = _get_embedding_model()
        new_emb = _encode_texts(
            model,
            new_texts,
            show_progress=verbose and len(new_texts) > 50,
        )
        full = np.vstack([embeddings, new_emb])
        _save_cached_embeddings(signature, full)
        if verbose:
            print(f"Embeddings: incremental update ({len(new_texts)} new row(s)).")
        return full
    except Exception:
        return None


def _merge_cache_meta(**updates):
    meta = _read_cache_meta() or {}
    meta.update(updates)
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(METADATA_CACHE_PATH, "w", encoding="utf-8") as fp:
        json.dump(meta, fp)


def _save_cached_embeddings(signature, embeddings):
    if os.path.isfile(CACHE_DIR):
        raise OSError(
            f"{CACHE_DIR} is a file, not a folder. Delete or rename it so embeddings can be saved."
        )
    os.makedirs(CACHE_DIR, exist_ok=True)
    np.save(EMBEDDINGS_CACHE_PATH, embeddings)
    _merge_cache_meta(dataset_signature=signature, rows=int(embeddings.shape[0]))


def _resolve_embeddings(df, signature, *, verbose=True):
    expected_rows = len(df)
    cached = _load_cached_embeddings(signature, expected_rows)
    if cached is not None:
        if verbose:
            print("Embeddings: loaded from cache.")
        return cached

    incremental = _try_incremental_embeddings(df, signature, expected_rows, verbose=verbose)
    if incremental is not None:
        return incremental

    if verbose:
        print(
            f"Embeddings: full encode ({expected_rows} rows, batch size {_get_encode_batch_size()}) — "
            "runs once per dataset version; interrupting skips saving the cache."
        )
    model = _get_embedding_model()
    embed_inputs = [_text_for_embedding(t) for t in df["featureText"].tolist()]
    embeddings = _encode_texts(model, embed_inputs, show_progress=verbose)
    _save_cached_embeddings(signature, embeddings)
    return embeddings


def _load_tfidf_cache(signature, expected_rows):
    if not (os.path.exists(TFIDF_WORD_CACHE_PATH) and os.path.exists(TFIDF_CHAR_CACHE_PATH)):
        return None
    try:
        meta = _read_cache_meta()
        if meta is None or meta.get("dataset_signature") != signature:
            return None
        word = np.load(TFIDF_WORD_CACHE_PATH)
        char = np.load(TFIDF_CHAR_CACHE_PATH)
        if int(word["rows"]) != expected_rows or int(char["rows"]) != expected_rows:
            return None
        from scipy import sparse

        word_matrix = sparse.csr_matrix((word["data"], word["indices"], word["indptr"]), shape=tuple(word["shape"]))
        char_matrix = sparse.csr_matrix((char["data"], char["indices"], char["indptr"]), shape=tuple(char["shape"]))
        return word_matrix, char_matrix
    except Exception:
        return None


def _save_tfidf_cache(word_matrix, char_matrix):
    os.makedirs(CACHE_DIR, exist_ok=True)
    for path, matrix in ((TFIDF_WORD_CACHE_PATH, word_matrix), (TFIDF_CHAR_CACHE_PATH, char_matrix)):
        matrix = matrix.tocsr()
        np.savez_compressed(
            path,
            data=matrix.data,
            indices=matrix.indices,
            indptr=matrix.indptr,
            shape=np.array(matrix.shape),
            rows=matrix.shape[0],
        )


def _save_tfidf_vectorizers(word_tfidf, char_tfidf):
    import joblib

    os.makedirs(CACHE_DIR, exist_ok=True)
    joblib.dump(word_tfidf, TFIDF_WORD_VECTORIZER_PATH)
    joblib.dump(char_tfidf, TFIDF_CHAR_VECTORIZER_PATH)


def _load_tfidf_vectorizers():
    import joblib

    if not (
        os.path.exists(TFIDF_WORD_VECTORIZER_PATH)
        and os.path.exists(TFIDF_CHAR_VECTORIZER_PATH)
    ):
        return None
    try:
        return joblib.load(TFIDF_WORD_VECTORIZER_PATH), joblib.load(TFIDF_CHAR_VECTORIZER_PATH)
    except Exception:
        return None


def _try_incremental_tfidf(df, signature, expected_rows, *, verbose=True):
    """Re-transform lyrics with saved vectorizers when only new rows were appended."""
    meta = _read_cache_meta()
    if meta is None:
        return None

    tfidf_signature = meta.get("tfidf_signature")
    tfidf_rows = meta.get("tfidf_rows")
    if tfidf_signature is None or tfidf_rows is None:
        return None
    tfidf_rows = int(tfidf_rows)
    if expected_rows <= tfidf_rows or expected_rows - tfidf_rows > _MAX_INCREMENTAL_ROWS:
        return None

    vectorizers = _load_tfidf_vectorizers()
    if vectorizers is None:
        return None

    try:
        if _get_dataset_signature(df, tfidf_rows) != tfidf_signature:
            return None
        word_tfidf, char_tfidf = vectorizers
        texts = df["featureText"].tolist()
        word_matrix = word_tfidf.transform(texts)
        char_matrix = char_tfidf.transform(texts)
        _save_tfidf_cache(word_matrix, char_matrix)
        _merge_cache_meta(tfidf_signature=signature, tfidf_rows=expected_rows)
        if verbose:
            print(f"TF-IDF: incremental transform ({expected_rows - tfidf_rows} new row(s)).")
        return word_matrix, char_matrix
    except Exception:
        return None


def _compute_tfidf_scores(df, anchor_id, signature, *, verbose=True):
    expected_rows = len(df)
    cached = _load_tfidf_cache(signature, expected_rows)
    if cached is not None:
        word_matrix, char_matrix = cached
    else:
        incremental = _try_incremental_tfidf(df, signature, expected_rows, verbose=verbose)
        if incremental is not None:
            word_matrix, char_matrix = incremental
        else:
            if verbose:
                print(f"TF-IDF: full fit ({expected_rows} rows).")
            word_tfidf = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), max_features=70000)
            word_matrix = word_tfidf.fit_transform(df["featureText"])
            char_tfidf = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, max_features=120000)
            char_matrix = char_tfidf.fit_transform(df["featureText"])
            _save_tfidf_vectorizers(word_tfidf, char_tfidf)
            _save_tfidf_cache(word_matrix, char_matrix)
            _merge_cache_meta(tfidf_signature=signature, tfidf_rows=expected_rows)
    word_scores = cosine_similarity(word_matrix[anchor_id], word_matrix).flatten()
    char_scores = cosine_similarity(char_matrix[anchor_id], char_matrix).flatten()
    return word_scores, char_scores


def _is_prepared(df):
    return _PREPARED_COLUMNS.issubset(df.columns)


def prepare_df(df):
    df = df.copy()
    df["artist"] = df["artist"].fillna("").astype(str)
    df["song"] = df["song"].fillna("").astype(str)
    df["text"] = df["text"].fillna("").astype(str)

    df["artistCleaned"] = df["artist"].apply(clean)
    df["songCleaned"] = df["song"].apply(clean)
    df["textCleaned"] = df["text"].apply(clean_lyrics)
    df["combinedMeta"] = df["artistCleaned"] + " " + df["songCleaned"]
    df["featureText"] = (
        df["songCleaned"] + " " + df["songCleaned"] + " " + df["artistCleaned"] + " " + df["textCleaned"]
    )
    return df


def _dataset_mtime():
    try:
        return os.path.getmtime(DATASET_PATH)
    except OSError:
        return None


def _set_prepared_dataset(df):
    with _dataset_lock:
        _dataset_cache["df"] = df
        _dataset_cache["mtime"] = _dataset_mtime()


def load_prepared_dataset(*, force_reload=False):
    """Return the cleaned dataset, loading from CSV only when the file changes."""
    mtime = _dataset_mtime()
    with _dataset_lock:
        cached_df = _dataset_cache["df"]
        if (
            not force_reload
            and cached_df is not None
            and _dataset_cache["mtime"] == mtime
        ):
            return cached_df

    df = pd.read_csv(DATASET_PATH)
    df = prepare_df(df)
    _set_prepared_dataset(df)
    return df


def warm_dataset_cache(*, verbose=True):
    if verbose:
        print("Dataset: loading into memory...")
    load_prepared_dataset()
    if verbose:
        with _dataset_lock:
            rows = len(_dataset_cache["df"]) if _dataset_cache["df"] is not None else 0
        print(f"Dataset: ready ({rows} rows).")


def search(name, artist, *, verbose=True):
    if not name.strip() or not artist.strip():
        if verbose:
            print("Song and artist are required.")
        return None, None

    df = load_prepared_dataset()

    query = clean(artist + " " + name)
    match = process.extractOne(query, df["combinedMeta"].tolist(), scorer=fuzz.WRatio)
    if match is None:
        if verbose:
            print("Record Not Found")
        return None, None

    _, score, index = match
    if score > 88:
        row = df.iloc[index]
        if verbose:
            print("Record Found")
            print(row["artist"])
            print(row["song"])
        return df, int(index)

    if verbose:
        print("Record Not Found")
    try:
        song = genius.search_song(name, artist)
        if song and song.lyrics:
            record = {"artist": artist, "song": song.title, "text": song.lyrics}
            base_cols = ["artist", "song", "text"]
            df_to_save = pd.concat([df[base_cols], pd.DataFrame([record])], ignore_index=True)
            df_to_save.to_csv(DATASET_PATH, index=False)
            df = prepare_df(df_to_save)
            _set_prepared_dataset(df)
            if verbose:
                print("Added record")
            return df, int(df.index[-1])

        if verbose:
            print("Record Not Found from Genius")
        return None, None
    except Exception as e:
        if verbose:
            print("No records returned")
            print("Error found: " + str(e))
        return None, None


def recommend(df, id, *, verbose=True):
    if id is None or id < 0 or id >= len(df):
        if verbose:
            print("Invalid song selection.")
        return None

    if not _is_prepared(df):
        df = prepare_df(df)
    anchor_song = clean(df.iloc[id]["song"])
    anchor_artist = clean(df.iloc[id]["artist"])

    # Avoid duplicate rows dominating the top-k output.
    df = df.drop_duplicates(subset=["artistCleaned", "songCleaned"], keep="first").reset_index(drop=True)
    anchor_candidates = df[(df["songCleaned"] == anchor_song) & (df["artistCleaned"] == anchor_artist)]
    if anchor_candidates.empty:
        if verbose:
            print("Could not locate selected track in processed dataset.")
        return None
    anchor_id = int(anchor_candidates.index[0])

    signature = _get_dataset_signature(df)
    embeddings = _resolve_embeddings(df, signature, verbose=verbose)
    word_scores, char_scores = _compute_tfidf_scores(df, anchor_id, signature, verbose=verbose)
    embed_scores = cosine_similarity([embeddings[anchor_id]], embeddings).flatten()

    same_artist_bonus = (df["artistCleaned"] == df.iloc[anchor_id]["artistCleaned"]).astype(float).values * 0.06
    same_title_penalty = (df["songCleaned"] == df.iloc[anchor_id]["songCleaned"]).astype(float).values * 0.25

    combined = (
        0.30 * _normalize_scores(word_scores)
        + 0.20 * _normalize_scores(char_scores)
        + 0.50 * _normalize_scores(embed_scores)
        + same_artist_bonus
        - same_title_penalty
    )
    combined[anchor_id] = -1e9

    top_indices = combined.argsort()[-TOP_K:][::-1]
    results = []
    for rank, record_id in enumerate(top_indices, 1):
        row = df.iloc[record_id]
        item = {
            "rank": rank,
            "artist": str(row["artist"]),
            "song": str(row["song"]),
            "score": float(combined[record_id]),
        }
        results.append(item)
        if verbose:
            print(f"{rank}: {item['artist']} - {item['song']} ({item['score']:.4f})")
    return results


if __name__ == "__main__":
    if HF_TOKEN:
        print("Hugging Face Hub: token found in environment (HF_TOKEN or HUGGING_FACE_HUB_TOKEN).")
    else:
        print(
            "Hugging Face Hub: no token in this process — set HF_TOKEN or HUGGING_FACE_HUB_TOKEN, "
            "then restart Cursor/terminal so it inherits Windows user env vars."
        )
    print(">>>")
    songName = input("Enter song name: ")
    artistName = input("Enter artist name: ")
    df, id = search(songName, artistName)
    if df is not None:
        recommend(df, id, verbose=True)
