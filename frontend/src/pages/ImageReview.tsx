import ImageReviewPanel from '../components/ImageReviewPanel';
import { useReviewTasks } from '../hooks/useApi';

export default function ImageReview() {
  const { data: tasks, isLoading } = useReviewTasks({ status: 'pending', kind: 'images', limit: 20 });

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-8 w-48 bg-[#1a1a1a] rounded" />
        {[1, 2].map((i) => <div key={i} className="h-56 bg-[#1a1a1a] rounded-lg" />)}
      </div>
    );
  }

  if (!tasks || tasks.length === 0) {
    return (
      <div>
        <h2 className="text-xl font-semibold text-white mb-6">Image Review</h2>
        <p className="text-gray-500">No runs with images to review.</p>
      </div>
    );
  }

  return (
    <div>
      <h2 className="text-xl font-semibold text-white mb-6">Image Review</h2>
      <div className="space-y-8">
        {tasks.map((task) => (
          <ImageReviewPanel
            key={task.id}
            runId={task.run_id}
            currentStep={task.current_step}
            title={task.title}
            channelName={task.channel_name}
            showRunHeader
          />
        ))}
      </div>
    </div>
  );
}
