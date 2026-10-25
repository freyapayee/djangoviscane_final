#!/usr/bin/env python3
"""Export the local trained ResNet18 checkpoint as a self-contained Android model.

Run using the project virtual environment after installing requirements-android-export.txt.
No training is performed and the training repository is only read.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "android-offline/app/src/main/assets"
DEFAULT_ARTIFACTS = ROOT.parent / "viscane_training/sugarcane_artifacts (2)/resnet18"
VARIETIES = {"524": 0, "847": 1, "947": 1, "MAURITIO": 2}
MATURITIES = {"NOT_MATURE": 1, "MATURE": 2, "OVER_MATURE": 3}


def decode_classes(classes):
    decoded = []
    for label in classes:
        parts = label.strip().split("__")
        if len(parts) != 2 or parts[0].upper() not in VARIETIES or parts[1].strip() not in MATURITIES:
            raise ValueError(f"Unsupported joint variety/maturity label: {label!r}")
        decoded.append({"label": label, "variety_index": VARIETIES[parts[0].upper()],
                        "maturity_index": MATURITIES[parts[1].strip()]})
    return decoded


def prepare(artifacts, images=()):
    import numpy as np
    import onnx
    import onnxruntime as ort
    import torch
    import torch.nn.functional as functional
    from torchvision.models import resnet18
    from PIL import Image

    artifacts = Path(artifacts)
    checkpoint_path = artifacts / "best_model.pt"
    original_metadata = json.loads((artifacts / "resnet18_android_metadata.json").read_text())
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    classes = list(checkpoint["classes"])
    size = int(checkpoint["image_size"])
    if classes != original_metadata["classes"] or size != original_metadata["image_size"]:
        raise ValueError("Checkpoint and Android metadata do not match.")
    decoded = decode_classes(classes)
    mean = original_metadata["normalization_mean"]
    std = original_metadata["normalization_std"]
    if mean != [0.485, 0.456, 0.406] or std != [0.229, 0.224, 0.225]:
        raise ValueError("Normalization changed; update the Android preprocessor.")
    model = resnet18(weights=None, num_classes=len(classes)).eval()
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    torch.set_num_threads(2)
    ASSETS.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        exported = Path(directory) / "sugarcane_resnet18.onnx"
        with torch.no_grad():
            torch.onnx.export(model, torch.zeros(1, 3, size, size), str(exported),
                              input_names=["images"], output_names=["logits"],
                              opset_version=17, dynamo=False, external_data=False)
        graph = onnx.load(str(exported))
        onnx.checker.check_model(graph)
        if any(t.data_location == onnx.TensorProto.EXTERNAL for t in graph.graph.initializer):
            raise ValueError("Model still references external weights.")
        session = ort.InferenceSession(str(exported), providers=["CPUExecutionProvider"])
        if session.get_inputs()[0].shape != [1, 3, size, size]:
            raise ValueError("Unexpected model input shape.")
        if session.get_outputs()[0].shape != [1, len(classes)]:
            raise ValueError("Unexpected model output shape.")
        rng = np.random.default_rng(42)
        cases = [("synthetic_" + str(i), rng.normal(size=(1, 3, size, size)).astype(np.float32))
                 for i in range(3)]
        for image_path in images:
            # Match train.py:_prepare_images_on_device(training=False): RGB,
            # float 0..1, direct bilinear resize (no antialias), ImageNet normalization.
            with Image.open(image_path) as image:
                array = np.array(image.convert("RGB"), copy=True)
            tensor = torch.from_numpy(array).permute(2, 0, 1).float().unsqueeze(0) / 255.0
            tensor = functional.interpolate(tensor, size=(size, size), mode="bilinear", align_corners=False)
            tensor = (tensor - torch.tensor(mean).view(1, 3, 1, 1)) / torch.tensor(std).view(1, 3, 1, 1)
            cases.append((Path(image_path).name, tensor.numpy()))
        checks = []
        for name, batch in cases:
            with torch.no_grad():
                expected = model(torch.from_numpy(batch)).numpy()
            actual = session.run(["logits"], {"images": batch})[0]
            np.testing.assert_allclose(actual, expected, rtol=1e-4, atol=1e-4)
            if actual.argmax() != expected.argmax():
                raise ValueError("Converted model predicted a different class.")
            checks.append({"case": name, "max_absolute_logit_error": float(np.abs(actual - expected).max()),
                           "predicted_class": classes[int(actual.argmax())]})
        metadata = {
            "schema_version": 1, "model_type": "resnet18", "model_file": exported.name,
            "model_sha256": hashlib.sha256(exported.read_bytes()).hexdigest(),
            "checkpoint_sha256": hashlib.sha256(checkpoint_path.read_bytes()).hexdigest(),
            "classes": classes, "class_mapping": decoded, "image_size": size,
            "input_name": "images", "input_shape": [1, 3, size, size], "output_name": "logits",
            "output_type": "logits", "normalization_mean": mean, "normalization_std": std,
            "resize": "bilinear_align_corners_false_no_antialias",
            "image_orientation": "raw_decoded_pixels_matching_training_api",
            "source": "viscane_training/sugarcane_artifacts (2)/resnet18/best_model.pt",
            "conversion_checks": checks,
            "limitations": ["No Mauritio NOT_MATURE class exists in this checkpoint.",
                            "Confidence is a model score, not measured accuracy or an out-of-distribution detector.",
                            "Android device parity and field validation are still required."],
        }
        shutil.copyfile(exported, ASSETS / exported.name)
        (ASSETS / "recognition-model.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2))
    return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts-dir", type=Path, default=DEFAULT_ARTIFACTS)
    parser.add_argument("--image", action="append", type=Path, default=[],
                        help="Optional real photo for checkpoint/ONNX parity; may be repeated")
    args = parser.parse_args()
    prepare(args.artifacts_dir, args.image)
