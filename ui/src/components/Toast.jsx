import { useEffect } from 'react';
import { AlertCircle, CheckCircle2, X } from 'lucide-react';

export default function Toast({ message, type = 'success', onClose }) {
  const isError = type === 'error';

  useEffect(() => {
    if (!message || isError) return;
    const timer = window.setTimeout(onClose, 2800);
    return () => window.clearTimeout(timer);
  }, [message, isError, onClose]);

  if (!message) return null;

  const Icon = isError ? AlertCircle : CheckCircle2;

  return (
    <div className={`toast${isError ? ' is-error' : ''}`} role={isError ? 'alert' : 'status'} aria-live={isError ? 'assertive' : 'polite'}>
      <Icon size={15} aria-hidden="true" />
      <span>{message}</span>
      <button type="button" aria-label="关闭提示" onClick={onClose}>
        <X size={13} aria-hidden="true" />
      </button>
    </div>
  );
}
