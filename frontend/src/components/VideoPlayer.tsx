interface VideoPlayerProps {
  runId: number;
  thumbnailPath?: string | null;
}

export default function VideoPlayer({ runId, thumbnailPath }: VideoPlayerProps) {
  const videoSrc = `/api/videos/${runId}/stream`;
  const posterSrc = thumbnailPath ? `/api/videos/${runId}/thumbnail` : undefined;

  return (
    <div className="relative rounded-lg overflow-hidden bg-black aspect-video">
      <video
        className="w-full h-full"
        controls
        preload="metadata"
        poster={posterSrc}
        src={videoSrc}
      >
        <source src={videoSrc} type="video/mp4" />
        Your browser does not support the video element.
      </video>
    </div>
  );
}
