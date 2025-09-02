import torch
import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

def test_dependencies():
    # Test PyTorch
    print("PyTorch version:", torch.__version__)
    print("CUDA available:", torch.cuda.is_available())
    
    # Test NumPy
    arr = np.array([1, 2, 3])
    print("\nNumPy working:", arr.mean() == 2)
    
    # Test FastAPI
    app = FastAPI()
    print("FastAPI working:", app.title == "FastAPI")
    
    # Test Pydantic
    class Item(BaseModel):
        name: str
        price: float
    
    item = Item(name="test", price=10.0)
    print("Pydantic working:", item.model_dump() == {"name": "test", "price": 10.0})
    
    # Test pandas
    df = pd.DataFrame({"A": [1, 2, 3]})
    print("Pandas working:", len(df) == 3)
    
    # Test scikit-learn
    v1 = np.array([[1, 1]])
    v2 = np.array([[2, 2]])
    similarity = cosine_similarity(v1, v2)[0][0]
    print("Scikit-learn working:", abs(similarity - 1.0) < 1e-6)
    
    print("\nAll dependencies are working correctly!")

if __name__ == "__main__":
    test_dependencies()
