import QrCode from 'components/qrCode';

type Props = {
  /** Already-encoded payload for a single QR code. */
  value: string;
  /** Rendered edge length in pixels. */
  size: number;
};

/** One chunk of the diagnostics capture. The rendering rules live in `QrCode`. */
function DiagnosticsQr({ value, size }: Props) {
  return <QrCode value={value} size={size} alt="Diagnostics payload" />;
}

export default DiagnosticsQr;
