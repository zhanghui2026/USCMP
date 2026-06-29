import { useState } from 'react';
import { getPartyColor } from '../constants';

interface Props {
  image_url?: string | null;
  display_name: string;
  party?: string;
  size?: number;
}

export default function MemberAvatar({ image_url, display_name, party, size = 32 }: Props) {
  const [imgError, setImgError] = useState(false);

  if (image_url && !imgError) {
    return (
      <img
        src={image_url}
        alt={display_name}
        onError={() => setImgError(true)}
        style={{
          width: size, height: size, borderRadius: '50%',
          objectFit: 'cover', flexShrink: 0,
        }}
      />
    );
  }

  return (
    <div style={{
      width: size, height: size, borderRadius: '50%',
      background: getPartyColor(party),
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      color: '#fff', fontWeight: 700, fontSize: Math.round(size * 0.45),
      flexShrink: 0,
    }}>
      {(display_name || '?').charAt(0)}
    </div>
  );
}
