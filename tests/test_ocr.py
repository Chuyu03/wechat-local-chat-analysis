from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from support import (  # noqa: F401 - installs src on sys.path
    REPOSITORY_ROOT,
    SYNTHETIC_PNG,
    register_synthetic_capture,
)
from wechat_analyse.ocr import (
    make_paddle_ocr,
    normalize_paddle_result,
    ocr_batch,
    resolve_requested_device,
)
from wechat_analyse.paths import init_batch


class _FakePaddleDevice:
    def __init__(self, cuda: bool) -> None:
        self._cuda = cuda

    def is_compiled_with_cuda(self) -> bool:
        return self._cuda


class _FakePaddle:
    def __init__(self, cuda: bool) -> None:
        self.device = _FakePaddleDevice(cuda)
        self.__version__ = "synthetic-paddle"


class _SyntheticImage:
    size = (1, 1)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None


class _SyntheticImageModule:
    @staticmethod
    def open(path: Path) -> _SyntheticImage:
        return _SyntheticImage()


class _FailingImageModule:
    @staticmethod
    def open(path: Path) -> _SyntheticImage:
        raise OSError("synthetic image metadata failure")


class _WorkingPaddleOcr:
    def __init__(self, **kwargs: object) -> None:
        self.device = str(kwargs["device"])

    def predict(self, path: str) -> object:
        return {
            "res": {
                "rec_texts": ["Synthetic registered screenshot"],
                "rec_scores": [0.99],
                "rec_polys": [[[1, 1], [2, 1], [2, 2], [1, 2]]],
            }
        }


class PaddleOcrCompatibilityTests(unittest.TestCase):
    def test_requires_completed_capture_and_coverage_acknowledgement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            paths = init_batch(
                workspace,
                "Synthetic Contact",
                "2040-01-01",
                "2040-01-02",
                batch_id="synthetic-incomplete-capture",
            )
            (paths.screenshots / "000001.png").write_bytes(SYNTHETIC_PNG)

            with self.assertRaises(ValueError):
                ocr_batch(paths.root, workspace)
            with self.assertRaises(RuntimeError):
                ocr_batch(
                    paths.root,
                    workspace,
                    capture_coverage_acknowledged=True,
                )

    def test_rejects_registered_screenshot_changed_after_capture(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            paths = init_batch(
                workspace,
                "Synthetic Contact",
                "2040-01-01",
                "2040-01-02",
                batch_id="synthetic-replaced-capture",
            )
            screenshot = paths.screenshots / "000001.png"
            screenshot.write_bytes(SYNTHETIC_PNG)
            register_synthetic_capture(workspace=workspace, batch_paths=paths)
            screenshot.write_bytes(b"synthetic replacement")

            with self.assertRaises(RuntimeError):
                ocr_batch(
                    paths.root,
                    workspace,
                    capture_coverage_acknowledged=True,
                )

    def test_ignores_unregistered_screenshot_after_validating_registered_set(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            paths = init_batch(
                workspace,
                "Synthetic Contact",
                "2040-01-01",
                "2040-01-02",
                batch_id="synthetic-unregistered-extra",
            )
            (paths.screenshots / "000001.png").write_bytes(SYNTHETIC_PNG)
            register_synthetic_capture(workspace=workspace, batch_paths=paths)
            (paths.screenshots / "000000.png").write_bytes(b"synthetic unregistered")

            ocr_batch(
                paths.root,
                workspace,
                device="cpu",
                limit=1,
                paddle_ocr_cls=_WorkingPaddleOcr,
                paddle_module=_FakePaddle(cuda=False),
                image_module=_SyntheticImageModule,
                capture_coverage_acknowledged=True,
            )

            manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))
        self.assertEqual(1, len(manifest["ocr"]["images"]))
        self.assertEqual(1, len(manifest["ocr"]["unregistered_files_ignored"]))
        self.assertTrue(
            manifest["ocr"]["images"][0]["source_image"].endswith("000001.png")
        )

    def test_normalizes_paddleocr_3_result_shape(self) -> None:
        payload = [
            {
                "res": {
                    "rec_texts": ["Synthetic hello", "Synthetic uncertain"],
                    "rec_scores": [0.99, 0.41],
                    "rec_polys": [
                        [[10, 10], [100, 10], [100, 30], [10, 30]],
                        [[10, 50], [180, 50], [180, 70], [10, 70]],
                    ],
                }
            }
        ]

        items = normalize_paddle_result(payload)

        self.assertEqual(["Synthetic hello", "Synthetic uncertain"], [item["text"] for item in items])
        self.assertEqual([0.99, 0.41], [item["confidence"] for item in items])
        self.assertEqual([1, 2], [item["index"] for item in items])

    def test_device_resolution_uses_paddleocr_3_device_spelling(self) -> None:
        self.assertEqual("cpu", resolve_requested_device("auto", _FakePaddle(cuda=False)))
        self.assertEqual("gpu:0", resolve_requested_device("auto", _FakePaddle(cuda=True)))
        self.assertEqual("cpu", resolve_requested_device("cpu", _FakePaddle(cuda=True)))
        self.assertEqual("gpu:0", resolve_requested_device("gpu:0", _FakePaddle(cuda=False)))

    def test_constructor_receives_explicit_paddleocr_3_device(self) -> None:
        calls: list[dict[str, object]] = []

        class FakePaddleOcr:
            def __init__(self, **kwargs: object) -> None:
                calls.append(kwargs)

        instance = make_paddle_ocr(FakePaddleOcr, "gpu:0")

        self.assertIsInstance(instance, FakePaddleOcr)
        self.assertEqual("gpu:0", calls[0]["device"])
        self.assertFalse(calls[0]["use_doc_orientation_classify"])
        self.assertFalse(calls[0]["use_doc_unwarping"])
        self.assertFalse(calls[0]["use_textline_orientation"])

    def test_auto_records_gpu_initialization_fallback_to_cpu(self) -> None:
        constructor_devices: list[str] = []

        class FakePaddleOcr:
            def __init__(self, **kwargs: object) -> None:
                device = str(kwargs["device"])
                constructor_devices.append(device)
                if device == "gpu:0":
                    raise RuntimeError("synthetic GPU initialization failure")

            def predict(self, path: str) -> object:
                return {
                    "res": {
                        "rec_texts": ["Synthetic CPU fallback result"],
                        "rec_scores": [0.99],
                        "rec_polys": [[[1, 1], [2, 1], [2, 2], [1, 2]]],
                    }
                }

        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            paths = init_batch(
                workspace,
                "Synthetic Contact",
                "2040-01-01",
                "2040-01-02",
                batch_id="synthetic-auto-fallback",
            )
            (paths.screenshots / "000001.png").write_bytes(SYNTHETIC_PNG)
            register_synthetic_capture(workspace=workspace, batch_paths=paths)

            ocr_batch(
                paths.root,
                workspace,
                device="auto",
                paddle_ocr_cls=FakePaddleOcr,
                paddle_module=_FakePaddle(cuda=True),
                image_module=_SyntheticImageModule,
                capture_coverage_acknowledged=True,
            )

            manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))
        self.assertEqual(["gpu:0", "cpu"], constructor_devices)
        self.assertEqual("auto", manifest["ocr"]["requested_device"])
        self.assertEqual("gpu:0", manifest["ocr"]["attempted_device"])
        self.assertEqual("cpu", manifest["ocr"]["actual_device"])
        self.assertIn("GPU initialization failed", manifest["ocr"]["fallback_reason"])
        self.assertIn("device=cpu", manifest["ocr"]["device_evidence"])

    def test_lazy_gpu_result_failure_falls_back_before_recording_actual_device(self) -> None:
        constructor_devices: list[str] = []

        class LazyPaddleOcr:
            def __init__(self, **kwargs: object) -> None:
                self.device = str(kwargs["device"])
                constructor_devices.append(self.device)

            def predict(self, path: str):
                if self.device == "gpu:0":
                    def failing_generator():
                        raise RuntimeError("synthetic lazy GPU failure")
                        yield None

                    return failing_generator()

                def cpu_generator():
                    yield {
                        "res": {
                            "rec_texts": ["Synthetic lazy CPU fallback"],
                            "rec_scores": [0.99],
                            "rec_polys": [[[1, 1], [2, 1], [2, 2], [1, 2]]],
                        }
                    }

                return cpu_generator()

        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            paths = init_batch(
                workspace,
                "Synthetic Contact",
                "2040-01-01",
                "2040-01-02",
                batch_id="synthetic-lazy-fallback",
            )
            (paths.screenshots / "000001.png").write_bytes(SYNTHETIC_PNG)
            register_synthetic_capture(workspace=workspace, batch_paths=paths)

            ocr_batch(
                paths.root,
                workspace,
                device="auto",
                paddle_ocr_cls=LazyPaddleOcr,
                paddle_module=_FakePaddle(cuda=True),
                image_module=_SyntheticImageModule,
                capture_coverage_acknowledged=True,
            )

            manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))
        self.assertEqual(["gpu:0", "cpu"], constructor_devices)
        self.assertEqual("cpu", manifest["ocr"]["actual_device"])
        self.assertEqual(["cpu"], manifest["ocr"]["actual_devices"])
        self.assertIn("GPU inference failed", manifest["ocr"]["fallback_reason"])

    def test_explicit_gpu_failure_does_not_fall_back(self) -> None:
        constructor_devices: list[str] = []

        class FailingGpuPaddleOcr:
            def __init__(self, **kwargs: object) -> None:
                constructor_devices.append(str(kwargs["device"]))
                raise RuntimeError("synthetic explicit GPU failure")

        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            paths = init_batch(
                workspace,
                "Synthetic Contact",
                "2040-01-01",
                "2040-01-02",
                batch_id="synthetic-explicit-gpu",
            )
            (paths.screenshots / "000001.png").write_bytes(SYNTHETIC_PNG)
            register_synthetic_capture(workspace=workspace, batch_paths=paths)

            with self.assertRaises(RuntimeError):
                ocr_batch(
                    paths.root,
                    workspace,
                    device="gpu:0",
                    paddle_ocr_cls=FailingGpuPaddleOcr,
                    paddle_module=_FakePaddle(cuda=True),
                    image_module=_SyntheticImageModule,
                    capture_coverage_acknowledged=True,
                )

            manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))
        self.assertEqual(["gpu:0"], constructor_devices)
        self.assertEqual("failed", manifest["ocr"]["status"])
        self.assertIsNone(manifest["ocr"]["fallback_reason"])
        self.assertIsNone(manifest["ocr"]["actual_device"])

    def test_post_inference_failure_marks_manifest_failed(self) -> None:
        class FakeCpuPaddleOcr:
            def __init__(self, **kwargs: object) -> None:
                pass

            def predict(self, path: str) -> object:
                return {
                    "res": {
                        "rec_texts": ["Synthetic result"],
                        "rec_scores": [0.99],
                        "rec_polys": [[[1, 1], [2, 1], [2, 2], [1, 2]]],
                    }
                }

        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            paths = init_batch(
                workspace,
                "Synthetic Contact",
                "2040-01-01",
                "2040-01-02",
                batch_id="synthetic-post-inference-failure",
            )
            (paths.screenshots / "000001.png").write_bytes(SYNTHETIC_PNG)
            register_synthetic_capture(workspace=workspace, batch_paths=paths)

            with self.assertRaises(OSError):
                ocr_batch(
                    paths.root,
                    workspace,
                    device="cpu",
                    paddle_ocr_cls=FakeCpuPaddleOcr,
                    paddle_module=_FakePaddle(cuda=False),
                    image_module=_FailingImageModule,
                    capture_coverage_acknowledged=True,
                )

            manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))
        self.assertEqual("failed", manifest["ocr"]["status"])
        self.assertIn("OCR processing failed", manifest["ocr"]["failure"])

    def test_empty_batch_fails_before_runtime_initialization(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            paths = init_batch(
                workspace,
                "Synthetic Contact",
                "2040-01-01",
                "2040-01-02",
                batch_id="synthetic-empty-ocr",
            )
            register_synthetic_capture(workspace=workspace, batch_paths=paths)

            with self.assertRaises(RuntimeError):
                ocr_batch(
                    paths.root,
                    workspace,
                    capture_coverage_acknowledged=True,
                )

            manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))
        self.assertEqual("failed", manifest["ocr"]["status"])
        self.assertIsNone(manifest["ocr"]["actual_device"])


if __name__ == "__main__":
    unittest.main()
