import os
import pickle
import torch
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModel
from tqdm import tqdm  # Optional: for a nice progress bar

# ideally, would need newer sentence-transformers
# but cannot because of VibeVoice experiments need transformers 4.51.3
# which break sentence-transformers;
# so we implement manual loading
# from sentence_transformers import SentenceTransformer, util

# --- CONFIGURATION ---
ROOT_DIRECTORY = "D:/progmars/Documents"  # Folder you want to index
INDEX_FILE = "file_index.pkl"      # Where to save the database
# MODEL = "sentence-transformers/all-MiniLM-L6-v2"
MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
# paraphrase-multilingual-MiniLM-L12-v2 for better Latvian language support

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"File index using device: {DEVICE}")

class SemanticFileSearchEngine:

    def __init__(self):
        print("Loading embedding model...")
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL)
        self.model = AutoModel.from_pretrained(MODEL)
        self.model.to(DEVICE)
        self.file_paths = []
        self.embeddings = None
        self.embedded_texts = []


    def scan_and_index(self):
        """Scans files and creates new embeddings."""
        print(f"Scanning directory: {ROOT_DIRECTORY}...")
        found_files = []
        texts_for_embedding = []
        for root, _, files in os.walk(ROOT_DIRECTORY):
            for file in files:
                # We store the full path, but index the filename + folder name context
                full_path = os.path.join(root, file)
                found_files.append(full_path)
                # Use basename and immediate parent folder for semantic embedding to avoid path noise
                parent = os.path.basename(root)
                basename = os.path.basename(full_path)
                stem, _ext = os.path.splitext(basename)
                # Normalize: replace separators with spaces, collapse repeats
                def normalize(s: str) -> str:
                    s = s.lower()
                    for ch in ['_', '-', '.', ',', '(', ')']: s = s.replace(ch, ' ')
                    return ' '.join(s.split())
                normalized = normalize(parent + ' ' + stem)
                texts_for_embedding.append(normalized)
        
        if not found_files:
            print("No files found!")
            return

        print(f"Embedding {len(found_files)} filenames (basename + parent)...")
        self.file_paths = found_files
        # Convert to tensor for fast search using cleaner names
        self.embedded_texts = texts_for_embedding
        self.embeddings = self.encode(texts_for_embedding) # Use our custom encode function
        self.save_index()


    def save_index(self):
        """Saves the paths and embeddings to disk."""
        with open(INDEX_FILE, 'wb') as f:
            pickle.dump({'paths': self.file_paths, 'embeddings': self.embeddings, 'texts': self.embedded_texts}, f)
        print(f"Index saved to {INDEX_FILE}")


    def load_index(self):
        """Loads the index from disk if it exists."""
        if os.path.exists(INDEX_FILE):
            print(f"Loading index from {INDEX_FILE}...")
            with open(INDEX_FILE, 'rb') as f:
                data = pickle.load(f)
                self.file_paths = data['paths']
                self.embeddings = data['embeddings']
                self.embedded_texts = data.get('texts', [])
            return True
        return False


    def search(self, query, top_k=5):
        """The core retrieval logic."""
        if self.embeddings is None:
            return []
        
        q = str(query).strip()
        if not q:
            return []
        # Apply the same normalization as indexing
        q_lower = q.lower()
        for ch in ['_', '-', '.', ',', '(', ')']: q_lower = q_lower.replace(ch, ' ')
        q_lower = ' '.join(q_lower.split())


        query_embedding = self.encode([q_lower])
        
        # Manual Cosine Similarity: (Query . Corpus_T)
        # Since vectors are normalized, dot product == cosine similarity
        scores = torch.mm(query_embedding, self.embeddings.transpose(0, 1))[0]
        
        top_results = torch.topk(scores, k=min(top_k, len(self.file_paths)))

        # keep debugging output
        for score, idx in zip(top_results.values, top_results.indices):
            print(score, self.file_paths[idx])

        # Return ranked top_k without hard threshold
        return [self.file_paths[idx] for idx in top_results.indices]


    ######################################
    # to replace sentence-transformers
    def mean_pooling(self, model_output, attention_mask):
        """
        This performs the 'magic' that sentence-transformers usually does.
        It averages the token vectors to get a single sentence vector.
        """
        token_embeddings = model_output.last_hidden_state
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)


    def encode(self, texts, batch_size=4096):
        """
        Encodes a list of texts in batches to prevent MemoryError.
        """
        all_embeddings = []
        
        # Loop through the texts in small chunks (batches)
        # Using tqdm gives you a progress bar so you know it's not frozen
        for i in tqdm(range(0, len(texts), batch_size), desc="Encoding batches"):
            batch_texts = texts[i : i + batch_size]
            
            # Tokenize just this small batch
            encoded_input = self.tokenizer(
                batch_texts, 
                padding=True, 
                truncation=True, 
                return_tensors='pt'
            )

            encoded_input = {k: v.to(DEVICE) for k, v in encoded_input.items()}

            # Compute embeddings for this batch
            with torch.no_grad():
                model_output = self.model(**encoded_input)

            # Pooling & Normalization
            sentence_embeddings = self.mean_pooling(model_output, encoded_input['attention_mask'])
            sentence_embeddings = F.normalize(sentence_embeddings, p=2, dim=1)
            
            # Store result and free memory immediately
            all_embeddings.append(sentence_embeddings)
            
        # Stack all small batches into one big tensor at the end
        if all_embeddings:
            return torch.cat(all_embeddings, dim=0)
        return None


############################
# --- 1. INITIALIZE THE SINGLETON ENGINE ---
# for tool call
engine = FileSearchEngine()

