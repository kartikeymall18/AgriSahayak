# Model report

This report describes models present in the AgriSahayak code. Model-weight files are intentionally not committed. External benchmark numbers below are attributed to their model cards; they are not represented as AgriSahayak's own benchmark.

| Model/component | Role in AgriSahayak | Classes / outputs | Reported evaluation |
|---|---|---|---|
| MobileNetV2 plant disease classifier | Classifies leaf images | 38 PlantVillage crop/health/disease labels | The upstream Hugging Face card reports 95.41% evaluation accuracy on its PlantVillage-derived evaluation set. This was not measured on AgriSahayak's camera or local images. |
| OpenAI CLIP ViT-B/32 | Zero-shot leaf/scene gate | Text-image similarity scores; not a disease classifier | No AgriSahayak accuracy score is claimed. |
| RT-DETR fruit detector | Finds supported produce, boxes and counts | 12 classes: apple, cherry, figs, olive, pomegranate, orange, rockmelon, strawberry, potato, tomato, watermelon, bell pepper | The upstream model card reports mAP@0.5:0.95 = 0.6524. It is an upstream report, not an independent AgriSahayak field benchmark. |
| Tomato fruit screen (optional local artifact) | Binary screen of the detected tomato region | Healthy-looking / possible issue / uncertain | Reproduced on the local held-out split of 79 images: accuracy 89.87%, macro-F1 89.10%, balanced accuracy 88.24%, at confidence threshold 0.68. This is a small prototype split; no named fruit disease is diagnosed. |

## Interpretation and limits

- The leaf model predicts one of its known labels. A high score does not prove the disease is present; a novel disease may be mapped to a familiar class.
- The upstream leaf benchmark is based on curated PlantVillage-style images. Controlled backgrounds differ from field photos with shadows, clutter, overlap, blur and varied cameras. Treat its reported accuracy as a dataset result, not expected field performance.
- RT-DETR produces boxes and object counts. Missed objects, duplicate boxes, occlusion and unsupported items can make counts wrong.
- The optional tomato screen is binary and region-level. It does not give per-tomato health labels, name a disease, confirm ripeness, freshness, food safety or pesticide residue.
- The app's tomato surface-color cue is a rough color estimate, not validated maturity analysis.
- The project does not claim a model for green chilli detection; the produce detector's supported class list contains bell pepper but not green chilli.
- Real deployment requires evaluation on consented, representative field images from the intended crops, locations, cameras and lighting. Keep person-identifiable images out of public test sets.

## Model and data sources

- [MobileNetV2 plant-disease model card](https://huggingface.co/linkanjarad/mobilenet_v2_1.0_224-plant-disease-identification): lists 38 classes and reports 95.41% accuracy. The pinned revision is `c1861579a670fb6232258805b801cd4137cb7176`; its license metadata is `other`, so do not redistribute the weights without reviewing permission.
- [RT-DETR fruit detector model card](https://huggingface.co/MohamedKhayat/fruit-detector-rtdetrv1-50-obj365): lists 12 produce classes, Apache-2.0 metadata and mAP 0.6524. The pinned revision is `2a21ec599f71c63a9cf5f8bff14126ea0c7444a1`.
- [OpenAI CLIP ViT-B/32](https://huggingface.co/openai/clip-vit-base-patch32): source for the optional zero-shot scene gate, pinned at `3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268`. Verify its usage terms before redistribution.
- Tomato-screen dataset: Jain, Nain and Jain, [TCP (Tomato-Chilli-Papaya Fruit & Leaf) Disease Dataset, version 4](https://data.mendeley.com/datasets/m4m6j2tjfj/4), CC BY 4.0 attribution required. The local training script and metrics document a 530-image cleaned set (372 train / 79 validation / 79 held-out test) and small-sample caveats. The actual image data and fine-tuned weights are not included in this public package.

## Reproducing / obtaining model files

Run `python download_models.py` from the repository root after installing the requirements to fetch the leaf classifier, CLIP gate and produce detector. The script pins the upstream revisions listed above. The tomato screen must be recreated locally following `model/tomato_fruit_disease/README.md`; no dataset or binary weight is bundled here.

