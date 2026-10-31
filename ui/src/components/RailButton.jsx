import { cx } from '../utils.js';

export default function RailButton({
  id,
  label,
  description,
  active = false,
  current = false,
  pressed,
  expanded,
  badge,
  onClick,
  children
}) {
  const tooltipId = `${id}-tooltip`;

  return (
    <button
      type="button"
      className={cx('rail-button', active && 'is-active')}
      aria-label={label}
      aria-describedby={tooltipId}
      aria-current={current ? 'page' : undefined}
      aria-pressed={pressed}
      aria-expanded={expanded}
      onClick={onClick}
    >
      {children}
      {badge ? <span className="rail-badge" aria-hidden="true">{badge}</span> : null}
      <span className="rail-tooltip" id={tooltipId} role="tooltip">
        <strong>{label}</strong>
        <span>{description}</span>
      </span>
    </button>
  );
}
