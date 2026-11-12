/**
 * Original companion artwork drawn for LeadRescue. Inboxic is an original lavender
 * fox character (not based on any existing franchise character). Locked companions
 * are shown only as simple silhouettes.
 */
interface Props {
  size?: number;
  className?: string;
  title?: string;
  withMail?: boolean;
}

export function Inboxic({ size = 160, className, title = "Inboxic, a lavender fox companion with a violet gem", withMail = true }: Props) {
  return (
    <svg viewBox="0 0 200 200" width={size} height={size} className={className} role="img" aria-label={title}>
      <defs>
        <radialGradient id="ibx-aura" cx="50%" cy="55%" r="50%">
          <stop offset="0%" stopColor="#c4b5fd" stopOpacity="0.55" />
          <stop offset="100%" stopColor="#c4b5fd" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="ibx-fur" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#cdbdfa" />
          <stop offset="100%" stopColor="#a78bfa" />
        </linearGradient>
      </defs>
      <circle cx="100" cy="112" r="92" fill="url(#ibx-aura)" />
      {/* tail: one broad crescent sweep */}
      <path d="M128 168 C178 166 192 112 166 78 C160 102 170 124 140 136 Z" fill="url(#ibx-fur)" />
      <path d="M166 78 C176 92 178 104 174 114 C166 104 160 94 166 78 Z" fill="#fdf4e3" />
      {/* body */}
      <ellipse cx="100" cy="148" rx="38" ry="38" fill="url(#ibx-fur)" />
      <path d="M76 124 L86 144 L93 131 L100 150 L107 131 L114 144 L124 124 Q100 114 76 124 Z" fill="#fdf4e3" />
      <ellipse cx="84" cy="183" rx="11" ry="7" fill="#fdf4e3" />
      <ellipse cx="116" cy="183" rx="11" ry="7" fill="#fdf4e3" />
      {/* ears */}
      <path d="M66 74 L48 10 L96 56 Z" fill="url(#ibx-fur)" />
      <path d="M68 66 L56 26 L86 55 Z" fill="#7c5cd6" />
      <path d="M134 74 L152 10 L104 56 Z" fill="url(#ibx-fur)" />
      <path d="M132 66 L144 26 L114 55 Z" fill="#7c5cd6" />
      {/* head with cheek tufts */}
      <path d="M60 86 C60 60 80 48 100 48 C120 48 140 60 140 86 L150 100 L134 104 C126 118 112 122 100 122 C88 122 74 118 66 104 L50 100 Z" fill="url(#ibx-fur)" />
      {/* forehead gem */}
      <path d="M100 54 L109 65 L100 77 L91 65 Z" fill="#7c3aed" stroke="#ede9fe" strokeWidth="1.5" />
      <path d="M100 57 L104 64 L100 66 Z" fill="#ede9fe" opacity="0.9" />
      {/* eyes */}
      <ellipse cx="83" cy="88" rx="7.5" ry="9.5" fill="#14183a" />
      <ellipse cx="117" cy="88" rx="7.5" ry="9.5" fill="#14183a" />
      <ellipse cx="83" cy="90" rx="4" ry="5" fill="#14b8a6" />
      <ellipse cx="117" cy="90" rx="4" ry="5" fill="#14b8a6" />
      <circle cx="85.5" cy="85" r="2.4" fill="#fff" />
      <circle cx="119.5" cy="85" r="2.4" fill="#fff" />
      {/* blush, nose, mouth */}
      <ellipse cx="72" cy="101" rx="6" ry="3.5" fill="#f9a8d4" opacity="0.55" />
      <ellipse cx="128" cy="101" rx="6" ry="3.5" fill="#f9a8d4" opacity="0.55" />
      <path d="M96 100 L104 100 L100 105 Z" fill="#14183a" />
      <path d="M100 105 Q96 110 92 107 M100 105 Q104 110 108 107" stroke="#14183a" strokeWidth="1.6" fill="none" strokeLinecap="round" />
      {withMail && (
        <g>
          <g transform="rotate(-14 34 52)">
            <rect x="20" y="42" width="28" height="20" rx="3" fill="#fff" stroke="#8b5cf6" strokeWidth="2" />
            <path d="M21 44 L34 54 L47 44" fill="none" stroke="#8b5cf6" strokeWidth="2" />
          </g>
          <g transform="rotate(12 172 36)">
            <rect x="160" y="28" width="24" height="17" rx="3" fill="#fff" stroke="#14b8a6" strokeWidth="2" />
            <path d="M161 30 L172 38 L183 30" fill="none" stroke="#14b8a6" strokeWidth="2" />
          </g>
        </g>
      )}
    </svg>
  );
}

const SILHOUETTES: Record<string, string> = {
  // Costchu: round body with tall pointed ears and a coin
  costchu: "M70 70 L60 20 L88 58 Q100 54 112 58 L140 20 L130 70 Q150 92 140 130 Q132 170 100 172 Q68 170 60 130 Q50 92 70 70 Z M140 140 a16 16 0 1 0 0.1 0 Z",
  // Vaultortle: domed shell turtle
  vaultortle: "M40 140 Q40 70 100 64 Q160 70 160 140 Z M150 120 Q176 104 178 82 Q166 70 152 84 Z M52 150 h20 v22 h-20 Z M128 150 h20 v22 h-20 Z",
  // Pingeot: bird with spread wings
  pingeot: "M100 60 Q120 60 122 84 L150 50 Q176 60 160 100 Q140 120 120 122 Q118 160 100 170 Q82 160 80 122 Q60 120 40 100 Q24 60 50 50 L78 84 Q80 60 100 60 Z",
  // Stockasaur: long-neck dinosaur with leaf and crate
  stockasaur: "M60 40 Q74 26 86 42 Q96 60 90 90 Q120 84 150 100 Q172 120 160 150 L150 172 h-18 l-4 -20 h-40 l-4 20 h-18 L60 140 Q50 110 66 92 Q60 70 60 40 Z M110 70 h34 v26 h-34 Z",
};

export function LockedSilhouette({ id, size = 120, name }: { id: string; size?: number; name: string }) {
  return (
    <svg viewBox="0 0 200 200" width={size} height={size} role="img" aria-label={`${name} silhouette, locked`}>
      <circle cx="100" cy="110" r="88" fill="#eef0f8" />
      <path d={SILHOUETTES[id] ?? SILHOUETTES.costchu} fill="#9aa1c2" fillRule="evenodd" />
      <text x="100" y="128" textAnchor="middle" fontSize="44" fontWeight="700" fill="#eef0f8" fontFamily="system-ui, sans-serif">
        ?
      </text>
    </svg>
  );
}

export function LogoMark({ size = 32 }: { size?: number }) {
  return (
    <svg viewBox="0 0 64 64" width={size} height={size} aria-hidden="true" focusable="false">
      <path d="M16 46h32a11 11 0 0 0 0-22 15 15 0 0 0-29-3 12 12 0 0 0-3 25z" fill="none" stroke="#2dd4bf" strokeWidth="5" strokeLinejoin="round" />
    </svg>
  );
}
