import argparse
import os
from pathlib import Path

# Note: You need to install byaldi and its dependencies.
# pip install byaldi pdf2image
# On Windows, pdf2image requires poppler to be installed and in your PATH.
# See: https://github.com/Belval/pdf2image#windows

try:
    from byaldi import RAGMultiModalModel
except ImportError:
    print("Error: The 'byaldi' package is not installed.")
    print("Please install it using: pip install byaldi pdf2image")
    exit(1)

def main():
    parser = argparse.ArgumentParser(description="Test ColPali for visual document embeddings using byaldi.")
    parser.add_argument("--pdf", type=str, required=True, help="Path to the annual report PDF to index.")
    parser.add_argument("--query", type=str, required=True, help="Question or query to search against the report.")
    parser.add_argument("--index_name", type=str, default="annual_report_index", help="Name for the local index.")
    
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"Error: The file {pdf_path} does not exist.")
        exit(1)

    print(f"Loading ColPali model (this might take a minute on first run to download weights)...")
    # Using a slightly smaller/standard version for testing
    model = RAGMultiModalModel.from_pretrained("vidore/colpali-v1.2")

    print(f"\nIndexing the document: {pdf_path}")
    print("This extracts pages as images and computes multi-vector embeddings for each page.")
    # Indexing creates a local directory with the `.byaldi` metadata and vector index
    model.index(
        input_path=str(pdf_path),
        index_name=args.index_name,
        store_collection_with_index=False,
        overwrite=True
    )
    print("Indexing complete!")

    print(f"\nSearching for: '{args.query}'")
    # Perform the visual search
    results = model.search(args.query, k=3)

    print("\n--- Top 3 Results ---")
    if not results:
        print("No results found.")
    else:
        for i, result in enumerate(results, 1):
            # result structure usually contains doc_id (page number) and score
            print(f"Result {i}:")
            print(f"  Page ID : {result.doc_id}")
            print(f"  Score   : {result.score:.4f}")
            print("-" * 20)
            
    print("\nNote: The page ID usually corresponds to the page number in the PDF where the answer visually resides.")

if __name__ == "__main__":
    main()
