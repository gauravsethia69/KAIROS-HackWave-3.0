import { Component } from 'react';
import type { ReactNode } from 'react';
import { ArrowUpRight, Grip, RotateCcw } from 'lucide-react';
import { registry } from '../widgets/registry';
import type { WidgetProps } from '../widgets/registry';
class WidgetBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? <div role="alert" className="empty"><p>This widget could not render.</p><button className="secondary" onClick={() => this.setState({ failed: false })}><RotateCcw size={14}/> Try again</button></div> : this.props.children; }
}
export function Workspace({ loading, error, onRetry, ...props }: Omit<WidgetProps, 'widget'> & { loading: boolean; error: string; onRetry: () => void }) {
  return <div className="workspace-grid" aria-busy={loading}>{[...props.plan.layout].sort((a, b) => a.order - b.order).map((widget, index) => {
    const Widget = registry[widget.type];
    return <section className={`widget size-${widget.size}`} key={`${widget.id}-${widget.type}`} style={{ animationDelay: `${index * 35}ms` }} aria-label={widget.title}><div className="widget-heading"><h2><Grip size={14}/>{widget.title}</h2><span className="widget-number">{String(index + 1).padStart(2, '0')}</span></div>{loading ? <div className="skeleton" role="status">Loading workspace data…</div> : error ? <div className="empty" role="alert"><p>{error}</p><button className="secondary" onClick={onRetry}>Retry loading</button></div> : <WidgetBoundary key={`${JSON.stringify(props.plan.filters)}-${props.plan.selectedEntityIds.join()}`}><Widget {...props} widget={widget}/></WidgetBoundary>}{widget.type === 'UsageChart' && !loading && !error && <button className="text-button chart-table" onClick={() => props.onIntent('Show usage as a table')}>Show as table <ArrowUpRight size={14}/></button>}</section>;
  })}</div>;
}
