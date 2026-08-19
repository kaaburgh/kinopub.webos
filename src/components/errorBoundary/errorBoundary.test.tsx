import React from 'react';
import ReactDOM from 'react-dom';

import ErrorBoundary from './errorBoundary';

import { logException } from 'utils/logging';

jest.mock('components/button', () => ({ children, onClick }: React.PropsWithChildren<{ onClick?: () => void }>) => (
  <button onClick={onClick}>{children}</button>
));

jest.mock('utils/logging', () => ({
  logException: jest.fn(),
}));

const mockedLogException = logException as jest.MockedFunction<typeof logException>;

describe('ErrorBoundary', () => {
  let container: HTMLDivElement;
  let consoleError: jest.SpyInstance;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    consoleError = jest.spyOn(console, 'error').mockImplementation(() => undefined);
    mockedLogException.mockClear();
  });

  afterEach(() => {
    ReactDOM.unmountComponentAtNode(container);
    container.remove();
    consoleError.mockRestore();
  });

  it('replaces a throwing child, reports it once, and leaves a reload action', () => {
    const error = new Error('render exploded');
    const reload = jest.fn();

    function ThrowingView(): never {
      throw error;
    }

    ReactDOM.render(
      <ErrorBoundary onReload={reload}>
        <ThrowingView />
      </ErrorBoundary>,
      container,
    );

    expect(container.textContent).toContain('Ошибка приложения');
    expect(mockedLogException).toHaveBeenCalledTimes(1);
    expect(mockedLogException).toHaveBeenCalledWith(error);

    const button = container.querySelector('button');
    expect(button).not.toBeNull();
    button?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    expect(reload).toHaveBeenCalledTimes(1);
  });
});
