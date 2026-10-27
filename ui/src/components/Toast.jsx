import { useEffect } from 'react';
import { CheckCircle2, X } from 'lucide-react';

export default function Toast({ message, onClose }) {
  useEffect(() => {
    if (!message) return;
    const timer = window.setTimeout(onClose, 2800);
    return () => window.clearTimeout(timer);
  }, [message, onClose]);

  if (!message) return null;

  return (
    <div className="toast" role="status" aria-live="polite">
      <CheckCircle2 size={15} aria-hidden="true" />
      <span>{message}</span>
      <button type="button" aria-label="关闭提示" onClick={onClose}>
        <X size={13} />
      </button>
    </div>
  );
}
