import React, { useEffect, useState } from 'react';
import { t } from '../lib/i18n';
import type { Language } from '../lib/types';

interface Props {
  score: number;
  size?: 'sm' | 'md' | 'lg';
  language: Language;
}

export function CommitmentRing({ score, size = 'md', language }: Props) {
  const [offset, setOffset] = useState(0);
  const safeScore = Math.max(0, Math.min(100, score));

  // Size mapping: [radius, strokeWidth, fontSize, containerSize]
  const sizeMap = {
    sm: { radius: 18, stroke: 3, font: 12, size: 44 },
    md: { radius: 28, stroke: 4, font: 16, size: 68 },
    lg: { radius: 40, stroke: 6, font: 24, size: 96 },
  };

  const { radius, stroke, font, size: containerSize } = sizeMap[size];
  const circumference = 2 * Math.PI * radius;
  const initialOffset = circumference;

  useEffect(() => {
    // Animate on mount
    setOffset(initialOffset);
    const timer = setTimeout(() => {
      const targetOffset = circumference - (safeScore / 100) * circumference;
      setOffset(targetOffset);
    }, 50); // slight delay to allow CSS transition to kick in
    return () => clearTimeout(timer);
  }, [safeScore, circumference, initialOffset]);

  let color = 'var(--danger)';
  let labelKey: Parameters<typeof t>[1] = 'commitment_label_poor';
  if (safeScore >= 70) {
    color = 'var(--success)';
    labelKey = safeScore >= 90 ? 'commitment_label_excellent' : 'commitment_label_good';
  } else if (safeScore >= 40) {
    color = 'var(--warning)';
    labelKey = 'commitment_label_fair';
  }

  const label = t(language, labelKey);

  return (
    <div className="commitment-ring-container" style={{ width: containerSize, height: containerSize }}>
      <svg className="commitment-ring-svg" width={containerSize} height={containerSize}>
        <circle
          className="commitment-ring-circle-bg"
          cx={containerSize / 2}
          cy={containerSize / 2}
          r={radius}
          strokeWidth={stroke}
        />
        <circle
          className="commitment-ring-circle-fg"
          cx={containerSize / 2}
          cy={containerSize / 2}
          r={radius}
          strokeWidth={stroke}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ stroke: color }}
        />
      </svg>
      <div className="commitment-ring-score" style={{ color, fontSize: `${font}px` }}>
        {safeScore}
      </div>
      {size !== 'sm' && (
        <div className="commitment-ring-label" style={{ color }}>
          {label}
        </div>
      )}
    </div>
  );
}
