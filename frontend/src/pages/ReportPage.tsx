import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ImagePlus,
  Send,
  CheckCircle2,
  Mic,
  Pencil,
  Trash2,
  Loader2,
  ArrowRight,
} from 'lucide-react';
import { VoiceRecorder } from '../components/VoiceRecorder';
import { LocationPicker } from '../components/LocationPicker';
import * as api from '../services/api';
import { WasteReport, VoiceTranscription } from '../types';

type Step = 'record' | 'details' | 'done';

export function ReportPage() {
  const [step, setStep] = useState<Step>('record');
  const [transcription, setTranscription] = useState<VoiceTranscription | null>(null);
  const [description, setDescription] = useState('');
  const [photo, setPhoto] = useState<File | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  const [location, setLocation] = useState<WasteReport['location'] | null>(null);
  const [address, setAddress] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [createdReport, setCreatedReport] = useState<WasteReport | null>(null);

  const handleVoiceComplete = async (blob: Blob) => {
    try {
      const result = await api.transcribeVoice(blob);
      setTranscription(result);
      setDescription(result.transcript);
      setStep('details');
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Transcription failed');
      setStep('details');
    }
  };

  const handleTypeInstead = () => {
    setStep('details');
  };

  const handlePhoto = (file: File | null) => {
    setPhoto(file);
    if (photoPreview) URL.revokeObjectURL(photoPreview);
    setPhotoPreview(file ? URL.createObjectURL(file) : null);
  };

  const canSubmit = description.trim().length >= 5 && location !== null && address.trim().length >= 3;

  const handleSubmit = async () => {
    if (!location) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const report = await api.processReport({
        lat: location.lat,
        lng: location.lng,
        address: address.trim(),
        description: description.trim(),
        image: photo,
      });
      setCreatedReport(report);
      setStep('done');
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Failed to submit report');
    } finally {
      setSubmitting(false);
    }
  };

  const resetAll = () => {
    setStep('record');
    setTranscription(null);
    setDescription('');
    handlePhoto(null);
    setLocation(null);
    setAddress('');
    setSubmitError(null);
    setCreatedReport(null);
  };

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-10">
      <div className="mb-8 text-center">
        <h1 className="text-2xl font-bold text-ink md:text-3xl">Report Waste</h1>
        <p className="mt-2 text-sm text-ink-mute">
          Fastest way: just speak. The AI listens, classifies the waste, and opens a ticket.
          Vendors can then buy it — and <span className="font-medium text-earth-700">you earn a commission</span>.
        </p>
      </div>

      {/* Step indicator */}
      <div className="mb-8 flex items-center justify-center gap-2 text-xs font-medium">
        {[
          { id: 'record', label: 'Describe' },
          { id: 'details', label: 'Details & Location' },
          { id: 'done', label: 'Ticket' },
        ].map((item, index) => {
          const order = ['record', 'details', 'done'];
          const active = order.indexOf(step) >= index;
          return (
            <div key={item.id} className="flex items-center gap-2">
              {index > 0 && <span className={`h-px w-8 ${active ? 'bg-forest-400' : 'bg-earth-200'}`} />}
              <span
                className={`rounded-full px-3 py-1 ${
                  active ? 'bg-forest-600 text-white' : 'bg-earth-100 text-ink-mute'
                }`}
              >
                {item.label}
              </span>
            </div>
          );
        })}
      </div>

      {step === 'record' && (
        <div className="space-y-5">
          <VoiceRecorder onComplete={handleVoiceComplete} />
          {submitError && (
            <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{submitError}</p>
          )}
          <div className="text-center">
            <p className="text-xs text-ink-mute">Prefer typing?</p>
            <button
              onClick={handleTypeInstead}
              className="mt-2 inline-flex items-center gap-2 rounded-lg border border-earth-200 bg-white px-4 py-2 text-sm font-medium text-ink-soft transition hover:border-forest-400 hover:text-forest-700"
            >
              <Pencil className="h-4 w-4" />
              Type my report instead
            </button>
          </div>
        </div>
      )}

      {step === 'details' && (
        <div className="space-y-6">
          {/* Transcript / description */}
          <section className="rounded-2xl border border-earth-100 bg-white p-5 shadow-card">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
                <Mic className="h-4 w-4 text-forest-600" />
                {transcription ? 'What we heard (edit if needed)' : 'Describe the waste'}
              </h2>
              <button
                onClick={() => { setStep('record'); setTranscription(null); setDescription(''); }}
                className="text-xs font-medium text-forest-700 hover:underline"
              >
                Re-record
              </button>
            </div>
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={4}
              placeholder="e.g. There is a big pile of plastic bottles behind the Nkwen market, blocking the drain…"
              className="w-full resize-none rounded-lg border border-earth-200 bg-cream px-3.5 py-3 text-sm text-ink outline-none transition focus:border-forest-500 focus:ring-2 focus:ring-forest-100"
            />
            {transcription && (
              <p className="mt-2 text-xs text-ink-faint">
                Transcribed by {transcription.provider}. You can correct any word before submitting.
              </p>
            )}
          </section>

          {/* Photo */}
          <section className="rounded-2xl border border-earth-100 bg-white p-5 shadow-card">
            <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink">
              <ImagePlus className="h-4 w-4 text-forest-600" />
              Photo <span className="font-normal text-ink-faint">(optional, improves AI accuracy)</span>
            </h2>
            {photoPreview ? (
              <div className="flex items-center gap-4">
                <img src={photoPreview} alt="Waste preview" className="h-24 w-24 rounded-lg object-cover" />
                <button
                  onClick={() => handlePhoto(null)}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-red-200 px-3 py-2 text-xs font-medium text-red-600 hover:bg-red-50"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Remove photo
                </button>
              </div>
            ) : (
              <label className="flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-earth-200 bg-earth-50/50 py-8 transition hover:border-forest-400">
                <ImagePlus className="h-7 w-7 text-ink-faint" />
                <span className="mt-2 text-xs text-ink-mute">Tap to add a photo of the waste</span>
                <input
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(event) => handlePhoto(event.target.files?.[0] ?? null)}
                />
              </label>
            )}
          </section>

          {/* Location */}
          <section className="rounded-2xl border border-earth-100 bg-white p-5 shadow-card">
            <h2 className="mb-3 text-sm font-semibold text-ink">Where is it?</h2>
            <LocationPicker
              value={location}
              onChange={setLocation}
              address={address}
              onAddressChange={setAddress}
            />
          </section>

          {submitError && (
            <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{submitError}</p>
          )}

          <button
            onClick={handleSubmit}
            disabled={!canSubmit || submitting}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-forest-600 py-3.5 text-sm font-semibold text-white shadow-lift transition hover:bg-forest-700 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {submitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Analyzing with AI…
              </>
            ) : (
              <>
                <Send className="h-4 w-4" />
                Submit Report
              </>
            )}
          </button>
          {!canSubmit && (
            <p className="text-center text-xs text-ink-mute">
              Add a description (min. 5 characters) and pick the location on the map.
            </p>
          )}
        </div>
      )}

      {step === 'done' && createdReport && (
        <div className="mx-auto max-w-md rounded-2xl border border-forest-200 bg-white p-8 text-center shadow-card">
          <span className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-forest-100">
            <CheckCircle2 className="h-9 w-9 text-forest-600" />
          </span>
          <h2 className="mt-4 text-xl font-bold text-ink">Report received!</h2>
          <p className="mt-1 text-sm text-ink-mute">
            The AI classified it and it is now live on the council dashboard and the marketplace.
          </p>
          <div className="mt-6 space-y-2 rounded-xl bg-cream p-4 text-left text-sm">
            <div className="flex justify-between">
              <span className="text-ink-mute">Ticket</span>
              <span className="font-semibold text-ink">{createdReport.ticket_id}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-ink-mute">Waste type</span>
              <span className="font-semibold capitalize text-ink">{createdReport.waste_type}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-ink-mute">Priority</span>
              <span className="font-semibold capitalize text-ink">{createdReport.priority}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-ink-mute">Location</span>
              <span className="max-w-[55%] truncate font-medium text-ink" title={createdReport.location.address}>
                {createdReport.location.address}
              </span>
            </div>
          </div>
          <p className="mt-4 rounded-lg bg-earth-50 px-4 py-3 text-xs leading-relaxed text-earth-800">
            💰 When a vendor reserves this waste, you get a <strong>10% commission</strong> of the deal
            — paid automatically when the collector delivers.
          </p>
          <div className="mt-6 flex flex-col gap-2 sm:flex-row">
            <Link
              to="/market"
              className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg bg-forest-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-forest-700"
            >
              See it on the Marketplace
              <ArrowRight className="h-4 w-4" />
            </Link>
            <button
              onClick={resetAll}
              className="rounded-lg border border-earth-200 px-4 py-2.5 text-sm font-medium text-ink-soft transition hover:border-forest-400"
            >
              Report another
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
