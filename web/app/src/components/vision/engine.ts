import "@tensorflow/tfjs";
import * as faceapi from "@vladmandic/face-api";

const MODEL_URL = (import.meta.env.VITE_FACE_MODEL_URL as string | undefined) || "/models";

let modelsLoaded = false;
let mobilenetLoaded = false;

export async function loadFaceModels(onProgress?: (msg: string) => void) {
  if (modelsLoaded) return;
  onProgress?.("Loading tiny-face detector");
  await faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL);
  try {
    onProgress?.("Loading mobilenet");
    await faceapi.nets.ssdMobilenetv1.loadFromUri(MODEL_URL);
    mobilenetLoaded = true;
  } catch (err) {
    console.warn("Mobilenet load failed, will rely on tinyFaceDetector", err);
  }
  onProgress?.("Loading landmarks");
  await faceapi.nets.faceLandmark68Net.loadFromUri(MODEL_URL);
  onProgress?.("Loading recognition");
  await faceapi.nets.faceRecognitionNet.loadFromUri(MODEL_URL);
  modelsLoaded = true;
}

export interface FaceBox {
  x: number;
  y: number;
  w: number;
  h: number;
  score?: number;
}

export interface DetectionResult {
  box: FaceBox;
  descriptor: number[];
}

export async function detectFaces(
  video: HTMLVideoElement,
  options: { minConfidence?: number } = {},
): Promise<DetectionResult[]> {
  if (!modelsLoaded) {
    await loadFaceModels();
  }
  let dets = await faceapi
    .detectAllFaces(
      video,
      new faceapi.TinyFaceDetectorOptions({
        inputSize: 416,
        scoreThreshold: options.minConfidence ?? 0.3,
      }),
    )
    .withFaceLandmarks()
    .withFaceDescriptors();
  if ((dets?.length ?? 0) === 0 && mobilenetLoaded) {
    dets = await faceapi
      .detectAllFaces(video, new faceapi.SsdMobilenetv1Options({ minConfidence: options.minConfidence ?? 0.25 }))
      .withFaceLandmarks()
      .withFaceDescriptors();
  }
  return dets.map((d) => ({
    box: {
      x: d.detection.box.x,
      y: d.detection.box.y,
      w: d.detection.box.width,
      h: d.detection.box.height,
      score: d.detection.score,
    },
    descriptor: Array.from(d.descriptor),
  }));
}
