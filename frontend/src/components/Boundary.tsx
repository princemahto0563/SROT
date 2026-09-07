import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";

/**
 * A rendering failure in one screen must not blank the whole console. The boundary
 * shows what went wrong on this screen and leaves navigation working.
 */
export class Boundary extends Component<
  { children: ReactNode; where: string },
  { error: Error | null }
> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`[SROT] render failure in ${this.props.where}`, error, info.componentStack);
  }

  componentDidUpdate(prev: { where: string }) {
    if (prev.where !== this.props.where && this.state.error) this.setState({ error: null });
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="rounded-xl border border-danger/35 bg-danger/[0.07] px-5 py-4">
        <div className="text-[13px] font-semibold text-danger">
          This screen could not be rendered
        </div>
        <p className="mt-1.5 max-w-[76ch] text-[11.5px] leading-relaxed text-ink2">
          The rest of the console is still usable — pick another screen in the sidebar. The error is
          shown here rather than swallowed, and the full stack is in the browser console.
        </p>
        <pre className="mt-3 max-h-40 overflow-auto rounded-lg border border-line bg-bg px-3 py-2.5 font-mono text-[10.5px] leading-relaxed text-danger">
{this.state.error.message}
        </pre>
        <button onClick={() => this.setState({ error: null })}
                className="btn btn-ghost mt-3 text-[11px]">
          Try rendering again
        </button>
      </div>
    );
  }
}
