import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { createAssessment, uploadVideo } from "../lib/api-client";
import type { CreateAssessmentRequest } from "../lib/api-types";
import UploadZone from "../components/UploadZone";

interface FormData {
  claim_number: string;
  agent_id: string;
  vehicle_year: string;
  vehicle_make: string;
  vehicle_model: string;
  vin: string;
}

const INITIAL_FORM: FormData = {
  claim_number: "",
  agent_id: "",
  vehicle_year: new Date().getFullYear().toString(),
  vehicle_make: "",
  vehicle_model: "",
  vin: "",
};

export default function NewAssessmentPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState<FormData>(INITIAL_FORM);
  const [exteriorFile, setExteriorFile] = useState<File | null>(null);
  const [interiorFile, setInteriorFile] = useState<File | null>(null);
  const [exteriorProgress, setExteriorProgress] = useState<number | null>(null);
  const [interiorProgress, setInteriorProgress] = useState<number | null>(null);
  const [formErrors, setFormErrors] = useState<Partial<Record<keyof FormData, string>>>({});

  const submitMutation = useMutation({
    mutationFn: async () => {
      // Validate
      const errors: Partial<Record<keyof FormData, string>> = {};
      if (!form.claim_number.trim()) errors.claim_number = "Required";
      if (!form.agent_id.trim()) errors.agent_id = "Required";
      if (!form.vehicle_make.trim()) errors.vehicle_make = "Required";
      if (!form.vehicle_model.trim()) errors.vehicle_model = "Required";
      const year = parseInt(form.vehicle_year, 10);
      if (isNaN(year) || year < 1900 || year > new Date().getFullYear() + 2) {
        errors.vehicle_year = "Invalid year";
      }

      if (Object.keys(errors).length > 0) {
        setFormErrors(errors);
        throw new Error("Please fix the form errors");
      }

      setFormErrors({});

      // 1. Create assessment
      const req: CreateAssessmentRequest = {
        claim_number: form.claim_number.trim(),
        agent_id: form.agent_id.trim(),
        vehicle_year: parseInt(form.vehicle_year, 10),
        vehicle_make: form.vehicle_make.trim(),
        vehicle_model: form.vehicle_model.trim(),
        vin: form.vin.trim() || undefined,
      };

      const assessment = await createAssessment(req);

      // 2. Upload videos in parallel
      const uploads: Promise<unknown>[] = [];

      if (exteriorFile) {
        setExteriorProgress(0);
        uploads.push(
          uploadVideo(assessment.id, "exterior", exteriorFile, setExteriorProgress)
        );
      }
      if (interiorFile) {
        setInteriorProgress(0);
        uploads.push(
          uploadVideo(assessment.id, "interior", interiorFile, setInteriorProgress)
        );
      }

      if (uploads.length > 0) {
        await Promise.all(uploads);
      }

      return assessment.id;
    },
    onSuccess: (assessmentId) => {
      navigate(`/assessments/${assessmentId}`);
    },
  });

  const updateField = (field: keyof FormData, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    if (formErrors[field]) {
      setFormErrors((prev) => {
        const next = { ...prev };
        delete next[field];
        return next;
      });
    }
  };

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-bold mb-1">New Assessment</h1>
      <p className="text-slate-400 text-sm mb-8">
        Create a new vehicle damage assessment
      </p>

      <div className="space-y-8">
        {/* Vehicle & claim info */}
        <section>
          <h2 className="text-lg font-semibold mb-4 text-slate-200">
            Claim Information
          </h2>
          <div className="grid grid-cols-2 gap-4">
            <FormField
              label="Claim Number"
              value={form.claim_number}
              onChange={(v) => updateField("claim_number", v)}
              error={formErrors.claim_number}
              placeholder="CLM-2024-001"
              required
            />
            <FormField
              label="Agent ID"
              value={form.agent_id}
              onChange={(v) => updateField("agent_id", v)}
              error={formErrors.agent_id}
              placeholder="AGT-001"
              required
            />
          </div>
        </section>

        <section>
          <h2 className="text-lg font-semibold mb-4 text-slate-200">
            Vehicle Details
          </h2>
          <div className="grid grid-cols-3 gap-4">
            <FormField
              label="Year"
              value={form.vehicle_year}
              onChange={(v) => updateField("vehicle_year", v)}
              error={formErrors.vehicle_year}
              placeholder="2024"
              required
            />
            <FormField
              label="Make"
              value={form.vehicle_make}
              onChange={(v) => updateField("vehicle_make", v)}
              error={formErrors.vehicle_make}
              placeholder="Toyota"
              required
            />
            <FormField
              label="Model"
              value={form.vehicle_model}
              onChange={(v) => updateField("vehicle_model", v)}
              error={formErrors.vehicle_model}
              placeholder="Camry"
              required
            />
          </div>
          <div className="mt-4 max-w-sm">
            <FormField
              label="VIN"
              value={form.vin}
              onChange={(v) => updateField("vin", v)}
              placeholder="Optional"
            />
          </div>
        </section>

        {/* Video uploads */}
        <section>
          <h2 className="text-lg font-semibold mb-4 text-slate-200">
            Video Uploads
          </h2>
          <div className="grid grid-cols-2 gap-6">
            <UploadZone
              label="Exterior Video"
              file={exteriorFile}
              uploadProgress={exteriorProgress}
              onFileSelect={setExteriorFile}
              onClear={() => {
                setExteriorFile(null);
                setExteriorProgress(null);
              }}
            />
            <UploadZone
              label="Interior Video"
              file={interiorFile}
              uploadProgress={interiorProgress}
              onFileSelect={setInteriorFile}
              onClear={() => {
                setInteriorFile(null);
                setInteriorProgress(null);
              }}
            />
          </div>
        </section>

        {/* Error display */}
        {submitMutation.error && (
          <div className="p-4 bg-red-900/30 border border-red-800 rounded-lg">
            <p className="text-sm text-red-400">
              {submitMutation.error instanceof Error
                ? submitMutation.error.message
                : "An error occurred"}
            </p>
          </div>
        )}

        {/* Submit */}
        <div className="flex items-center gap-4 pt-4 border-t border-slate-800">
          <button
            onClick={() => submitMutation.mutate()}
            disabled={submitMutation.isPending}
            className="flex items-center gap-2 px-6 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-600/50 text-white text-sm font-medium rounded-lg transition-colors"
          >
            {submitMutation.isPending ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Processing...
              </>
            ) : (
              "Create Assessment"
            )}
          </button>
          <button
            onClick={() => navigate("/assessments")}
            className="px-6 py-2.5 text-sm text-slate-400 hover:text-slate-200 transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

// -- Form field component ----------------------------------------------------

function FormField({
  label,
  value,
  onChange,
  error,
  placeholder,
  required,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  placeholder?: string;
  required?: boolean;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-slate-300 mb-1.5">
        {label}
        {required && <span className="text-red-400 ml-0.5">*</span>}
      </label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={`w-full px-3 py-2 bg-slate-800 border rounded-lg text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-1 ${
          error
            ? "border-red-500 focus:border-red-500 focus:ring-red-500"
            : "border-slate-700 focus:border-blue-500 focus:ring-blue-500"
        }`}
      />
      {error && <p className="text-xs text-red-400 mt-1">{error}</p>}
    </div>
  );
}
