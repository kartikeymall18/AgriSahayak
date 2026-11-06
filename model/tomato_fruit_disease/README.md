# AgriSahayak tomato fruit screening model

This is a local, binary image screen for tomato fruit photos. It returns either **likely healthy-looking**, **possible issue**, or **uncertain**. It does not identify a named disease and is not a replacement for the separate tomato-leaf disease classifier.

The screening result applies to the detected tomato region in the photo as a whole. It does not assign a health result to each individual tomato in a multi-fruit image. The produce detector independently draws boxes and estimates counts; the camera overlay labels each box with the tomato name and a rough surface-color cue.

## Training and evaluation

- Architecture: MobileNetV2 image classifier, fine-tuned from the existing AgriSahayak image-classifier weights.
- Tomato data: 530 unique images in the `Healthy Tomato` and `Disease Tomato` folders from the dataset below.
- Split: 372 train, 79 validation, 79 held-out test images, class-stratified after exact duplicate removal.
- Held-out test: 89.87% accuracy, 0.891 macro-F1, and 0.8824 balanced accuracy. This is a small prototype test split, not independent field validation.
- Confidence below 0.68 is shown as uncertain.

## Dataset attribution

Anand Kumar Jain, Neeta Nain, and Anadi Jain, **TCP (Tomato-Chilli-Papaya Fruit & Leaf) Disease Dataset**, Mendeley Data, version 4, DOI [10.17632/m4m6j2tjfj.4](https://doi.org/10.17632/m4m6j2tjfj.4), licensed under CC BY 4.0. The source also describes the related paper [10.21203/rs.3.rs-8819059/v1](https://doi.org/10.21203/rs.3.rs-8819059/v1).

The initialization weights are from the pre-existing AgriSahayak classifier, which was obtained from [linkanjarad/mobilenet_v2_1.0_224-plant-disease-identification](https://huggingface.co/linkanjarad/mobilenet_v2_1.0_224-plant-disease-identification). Its Hugging Face metadata lists the license as `other`; check the model card before redistributing these weights outside this project.

## Limits

The training set is small, and images captured by the rover may differ in lighting, background, camera distance, variety, and disease. A “likely healthy-looking” result is not proof the tomato is disease-free. A “possible issue” result is only a prompt to inspect it. The model does not diagnose tomato diseases by name, and it does not assess freshness, ripeness, pesticide residue, or food safety.
