/**
 * JSX type declarations for the @google/model-viewer web component.
 *
 * model-viewer is loaded from CDN as a custom element; React/TypeScript needs
 * these declarations to accept its attributes in JSX without type errors.
 */

declare namespace JSX {
  interface IntrinsicElements {
    "model-viewer": ModelViewerAttributes;
  }
}

interface ModelViewerAttributes
  extends React.DetailedHTMLProps<
    React.HTMLAttributes<HTMLElement>,
    HTMLElement
  > {
  src?: string;
  alt?: string;
  poster?: string;
  loading?: "auto" | "lazy" | "eager";

  // AR
  ar?: boolean;
  "ar-modes"?: string;
  "ar-scale"?: "auto" | "fixed";
  "ar-placement"?: "floor" | "wall";

  // Camera & interaction
  "camera-controls"?: boolean;
  "touch-action"?: string;
  "auto-rotate"?: boolean;
  "auto-rotate-delay"?: number;
  "rotation-per-second"?: string;
  "interaction-prompt"?: "auto" | "none";
  "interaction-prompt-threshold"?: number;

  // Camera position
  "camera-orbit"?: string;
  "camera-target"?: string;
  "field-of-view"?: string;
  "min-camera-orbit"?: string;
  "max-camera-orbit"?: string;
  "min-field-of-view"?: string;
  "max-field-of-view"?: string;

  // Lighting & environment
  "shadow-intensity"?: string;
  "shadow-softness"?: string;
  exposure?: string;
  "environment-image"?: string;

  // Sizing
  style?: React.CSSProperties;
}
