import { useState } from 'react';

interface VideoPlayerProps {
  runId: number;
  thumbnailPath?: string | null;
  aspectRatio?: string;
}

export default function VideoPlayer({ runId, thumbnailPath, aspectRatio }: VideoPlayerProps) {
  const videoSrc = `/api/videos/${runId}/stream`;
  const posterSrc = thumbnailPath ? `/api/videos/${runId}/thumbnail` : undefined;
  const [error, setError] = useState(false);

  const aspectClass = aspectRatio ? '' : 'aspect-video';

  if (error) {
    return (
      <div className={`relative rounded-lg overflow-hidden bg-[#1a1a1a] flex items-center justify-center ${aspectClass}`}
           style={aspectRatio ? { aspectRatio } : undefined}>
        <p className="text-gray-500 text-sm">Video file unavailable — run directory was cleaned up</p>
      </div>
    );
  }

  return (
    <div
      className={`relative rounded-lg overflow-hidden bg-black ${aspectClass}`}
      style={aspectRatio ? { aspectRatio } : undefined}
    >
      <video
        className="w-full h-full"
        controls
        preload="metadata"
        poster={posterSrc}
        onError={() => setError(true)}
      >
        <source src={videoSrc} type="video/mp4" />
      </video>
    </div>
  );
}
