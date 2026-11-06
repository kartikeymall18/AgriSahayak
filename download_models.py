"""Download AgriSahayak's three upstream vision models into local ignored folders."""
from pathlib import Path

from huggingface_hub import snapshot_download

ROOT = Path(__file__).resolve().parent
MODELS = (
    ("linkanjarad/mobilenet_v2_1.0_224-plant-disease-identification",
     "c1861579a670fb6232258805b801cd4137cb7176", ROOT / "model"),
    ("openai/clip-vit-base-patch32", "3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268",
     ROOT / "gate_model"),
    ("MohamedKhayat/fruit-detector-rtdetrv1-50-obj365",
     "2a21ec599f71c63a9cf5f8bff14126ea0c7444a1",
     ROOT / "model" / "produce-rtdetrv1-50-obj365"),
)


def main():
    for repo_id, revision, destination in MODELS:
        destination.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {repo_id} at {revision} -> {destination}")
        snapshot_download(repo_id=repo_id, revision=revision, local_dir=str(destination))
    print("Vision model downloads finished. Tomato fruit screening is an optional separate model; see its README.")


if __name__ == "__main__":
    main()

