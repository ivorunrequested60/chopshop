import { Component, ReactNode } from "react";

type Props = {
  children: ReactNode;
  fallback?: ReactNode;
};

type State = { hasError: boolean; message: string };

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, message: "" };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message };
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback ?? (
          <div className="flex h-full min-h-[120px] items-center justify-center rounded-lg border border-red-500/60 bg-red-950/60 p-4 text-xs text-red-200">
            Render error: {this.state.message}
          </div>
        )
      );
    }
    return this.props.children;
  }
}
