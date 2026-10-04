import { useCallback, useEffect, useRef, useState } from 'react';
import { Mic, Square, Loader2, RotateCcw } from 'lucide-react';

interface VoiceRecorderProps {
  onComplete: (blob: Blob, durationSeconds: number) => void;
  disabled?: boolean;
}

type RecorderState = 'idle' | 'recording' | 'processing' | 'error';

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export function VoiceRecorder({ onComplete, disabled = false }: VoiceRecorderProps) {
  const [state, setState] = useState<RecorderState>('idle');
  const [seconds, setSeconds] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<number | null>(null);

  const cleanup = useCallback(() => {
    if (timerRef.current) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }, []);

  useEffect(() => cleanup, [cleanup]);

  const startRecording = async () => {
    setErrorMessage(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];

      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/webm')
          ? 'audio/webm'
          : '';
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' });
        const duration = seconds;
        cleanup();
        setAudioUrl(URL.createObjectURL(blob));
        setState('processing');
        onComplete(blob, duration);
      };

      recorder.start();
      setSeconds(0);
      setState('recording');
      timerRef.current = window.setInterval(() => setSeconds((s) => s + 1), 1000);
    } catch {
      cleanup();
      setState('error');
      setErrorMessage('Microphone access was blocked. Allow the microphone and try again, or type your report.');
    }
  };

  const stopRecording = () => {
    mediaRecorderRef.current?.stop();
  };

  const reset = () => {
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    setAudioUrl(null);
    setSeconds(0);
    setErrorMessage(null);
    setState('idle');
  };

  return (
    <div className="rounded-2xl border border-earth-200 bg-earth-50/60 p-6 text-center">
      {state === 'idle' && (
        <>
          <button
            type="button"
            onClick={startRecording}
            disabled={disabled}
            className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-forest-600 text-white shadow-lift transition hover:bg-forest-700 disabled:opacity-50"
            aria-label="Start voice recording"
          >
            <Mic className="h-8 w-8" />
          </button>
          <p className="mt-4 text-sm font-medium text-ink-soft">
            Tap the microphone and describe the waste
          </p>
          <p className="mt-1 text-xs text-ink-mute">
            e.g. "There is a big pile of plastic bottles behind the Nkwen market"
          </p>
        </>
      )}

      {state === 'recording' && (
        <>
          <button
            type="button"
            onClick={stopRecording}
            className="mic-recording mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-red-600 text-white shadow-lift transition hover:bg-red-700"
            aria-label="Stop recording"
          >
            <Square className="h-7 w-7" />
          </button>
          <p className="mt-4 text-sm font-medium text-red-700">Recording… {formatDuration(seconds)}</p>
          <p className="mt-1 text-xs text-ink-mute">Speak clearly. Tap the square when done.</p>
        </>
      )}

      {state === 'processing' && (
        <>
          <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-earth-100">
            <Loader2 className="h-8 w-8 animate-spin text-earth-600" />
          </div>
          <p className="mt-4 text-sm font-medium text-ink-soft">Transcribing with ElevenLabs…</p>
          {audioUrl && (
            <audio controls src={audioUrl} className="mx-auto mt-3 h-10 w-full max-w-xs" />
          )}
        </>
      )}

      {state === 'error' && (
        <>
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-red-100">
            <RotateCcw className="h-7 w-7 text-red-600" />
          </div>
          <p className="mt-3 max-w-sm text-sm text-red-700">{errorMessage}</p>
          <button
            type="button"
            onClick={reset}
            className="mt-4 rounded-lg bg-forest-600 px-4 py-2 text-sm font-medium text-white hover:bg-forest-700"
          >
            Try Again
          </button>
        </>
      )}
    </div>
  );
}
