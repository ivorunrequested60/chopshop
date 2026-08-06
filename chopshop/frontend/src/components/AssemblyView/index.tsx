type Props = {
  jobId: string | null;
};

export function AssemblyView({ jobId }: Props) {
  if (!jobId) return null;

  return (
    <div>
      <h2>Assembly view</h2>
      <p>Exploded and assembled previews will be rendered here.</p>
    </div>
  );
}

