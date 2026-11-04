export default function TeamAgentIcon({ team, node, active = false, size = 20 }) {
  const tone = team || (node === 'verify' ? 'blue' : ['redteam-lab', 'redteam-agent'].includes(node) ? 'red' : null);
  if (!tone) return null;
  return (
    <svg className={`team-agent-icon team-agent-icon--${tone}${active ? ' is-active' : ''}`} width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">
      <path fill="currentColor" d="M12 2c-3 0-5 3.2-6.1 6.4L4.5 13l2.8 2.2C4.8 16.2 3 18.3 3 21h18c0-2.7-1.8-4.8-4.3-5.8l2.8-2.2-1.4-4.6C17 5.2 15 2 12 2Z" />
      <path fill="#101826" d="m7.4 9.5 4.6-2.6 4.6 2.6-.9 3.7-3.7 2.3-3.7-2.3Z" />
      <path d="m9 11.3 1.6.5m2.8 0 1.6-.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <rect x="5.5" y="17" width="13" height="5.5" rx="1" fill="#101826" stroke="currentColor" strokeWidth="1.4" />
      <path d="m10.8 18.8 1.3 1-1.3 1m2.2 0h1.2" stroke="currentColor" strokeWidth=".8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
