import React from 'react';

import Button from 'components/button';
import { logException } from 'utils/logging';

type Props = {
  children: React.ReactNode;
  /** Test seam; production falls back to a full page reload. */
  onReload?: () => void;
};

type State = {
  error?: Error;
};

/**
 * Keeps a render-time exception from turning the entire TV application into a black screen.
 *
 * React error boundaries deliberately cover render/lifecycle failures only. Event-handler and async
 * failures still belong to their own error paths; pretending this catches them would make the
 * fallback look more comprehensive than it is.
 */
class ErrorBoundary extends React.Component<Props, State> {
  state: State = {};

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error) {
    logException(error);
  }

  private reload = () => {
    if (this.props.onReload) {
      this.props.onReload();
      return;
    }

    window.location.reload();
  };

  render() {
    if (!this.state.error) {
      return this.props.children;
    }

    return (
      <div
        className="absolute top-0 right-0 bottom-0 left-0 flex items-center justify-center bg-black text-white"
        role="alert"
      >
        <div className="mx-8 flex max-w-3xl flex-col items-center px-8 py-6 text-center">
          <div className="mb-2 text-3xl font-bold">Ошибка приложения</div>
          <div className="mb-5 text-xl">Не удалось показать этот экран.</div>
          <Button className="bg-gray-800 text-green-400" icon="refresh" autoFocus onClick={this.reload}>
            Перезагрузить
          </Button>
        </div>
      </div>
    );
  }
}

export default ErrorBoundary;
