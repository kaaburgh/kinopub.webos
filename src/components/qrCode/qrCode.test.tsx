import React from 'react';
import ReactDOM from 'react-dom';

import QrCode from './qrCode';

describe('QrCode', () => {
  let container: HTMLDivElement;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  afterEach(() => {
    ReactDOM.unmountComponentAtNode(container);
    container.remove();
  });

  it.each([
    ['a lowercase URL in byte mode', 'https://kino.pub/device'],
    ['an alphanumeric payload', 'KPD1.ABCDEFGH234567'],
  ])('renders %s as one image', (_, value) => {
    ReactDOM.render(<QrCode value={value} size={280} alt="Ссылка" />, container);

    const images = container.querySelectorAll('img');

    expect(images).toHaveLength(1);
    expect(images[0].getAttribute('src')).toMatch(/^data:image\/gif;base64,/);
    expect(images[0].getAttribute('alt')).toBe('Ссылка');
    expect(images[0].style.width).toBe('280px');
  });

  it('says so instead of failing when the payload does not fit in one code', () => {
    ReactDOM.render(<QrCode value={'x'.repeat(4000)} size={280} alt="Ссылка" />, container);

    expect(container.querySelector('img')).toBeNull();
    expect(container.textContent).toBe('Не удалось построить QR-код');
  });
});
