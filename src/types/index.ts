export type Screen = 'home' | 'scan' | 'model' | 'reports';

export type CaptureMode = 'photo' | 'video';

export type DamageSeverity = 'high' | 'medium' | 'low' | 'clear';

export interface DamageZone {
  id: string;
  name: string;
  severity: DamageSeverity;
  description: string;
}

export interface AssessmentResult {
  id: string;
  vehicleName: string;
  analyzedAt: string;
  overallSeverity: DamageSeverity;
  summary: string;
  zones: DamageZone[];
}

export interface RecentAssessment {
  id: string;
  vehicleName: string;
  subtitle: string;
  status: 'done' | 'processing' | 'failed';
  timestamp: string;
}

export interface UploadState {
  status: 'idle' | 'uploading' | 'processing' | 'done' | 'error';
  progress: number;
  message: string;
}
