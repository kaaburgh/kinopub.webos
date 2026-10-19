import React from 'react';
import ReactDOM from 'react-dom';

import PairView, { DEFAULT_VERIFICATION_URI } from './pair';

const mockSearchParams: Record<string, string | undefined> = {};

jest.mock('hooks/useSearchParam', () => (param: string) => mockSearchParams[param]);
jest.mock('components/seo', () => () => null);
jest.mock('components/qrCode', () => ({ value, alt }: { value: string; alt: string }) => <img alt={alt} data-value={value} />);

describe('PairView', () => {
  let container: HTMLDivElement;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  afterEach(() => {
    ReactDOM.unmountComponentAtNode(container);
    container.remove();
    Object.keys(mockSearchParams).forEach((key) => delete mockSearchParams[key]);
  });

  it('shows the code and puts the verification address the API sent into the QR code', () => {
    mockSearchParams.userCode = 'ABC123';
    mockSearchParams.verificationUri = 'https://kino.pub/device';

    ReactDOM.render(<PairView />, container);

    expect(container.textContent).toContain('ABC123');
    expect(container.textContent).toContain('https://kino.pub/device');
    expect(container.querySelector('img')?.getAttribute('data-value')).toBe('https://kino.pub/device');
  });

  it('falls back to the default address for both the text and the QR code', () => {
    mockSearchParams.userCode = 'ABC123';

    ReactDOM.render(<PairView />, container);

    expect(container.textContent).toContain(DEFAULT_VERIFICATION_URI);
    expect(container.querySelector('img')?.getAttribute('data-value')).toBe(DEFAULT_VERIFICATION_URI);
  });

  it('does not put the pairing code into the QR code', () => {
    mockSearchParams.userCode = 'ABC123';
    mockSearchParams.verificationUri = 'https://kino.pub/device';

    ReactDOM.render(<PairView />, container);

    expect(container.querySelector('img')?.getAttribute('data-value')).not.toContain('ABC123');
  });
});
