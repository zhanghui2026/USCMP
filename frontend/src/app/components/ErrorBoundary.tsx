import { Component, type ReactNode } from 'react';
import { Button, Result } from 'antd';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div style={{ padding: 24, display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
          <Result
            status="error"
            title="组件渲染异常"
            subTitle={this.state.error?.message || '未知错误'}
            extra={
              <Button type="primary" onClick={() => this.setState({ hasError: false, error: null })}>
                重试
              </Button>
            }
          />
        </div>
      );
    }
    return this.props.children;
  }
}
