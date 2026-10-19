import QrCode from 'components/qrCode';
import Seo from 'components/seo';
import useSearchParam from 'hooks/useSearchParam';

export const DEFAULT_VERIFICATION_URI = 'https://kino.pub/device';

/** Large enough to scan from the sofa; the URL needs only a small code, so modules stay coarse. */
const QR_SIZE = 280;

const PairView: React.FC = () => {
  const userCode = useSearchParam('userCode');
  const verificationUri = useSearchParam('verificationUri') || DEFAULT_VERIFICATION_URI;

  return (
    <>
      <Seo title="Авторизация" />
      <div className="w-screen h-screen flex justify-center items-center text-gray-200 text-center">
        <div>
          Подтвердите устройство перейдя по ссылке:
          <br />
          {verificationUri}
          <br />
          и введите код:
          <br />
          {userCode}
        </div>
        {/* Only the page address: whether the KinoPub page accepts the code in the URL is unknown. */}
        <div className="ml-16 flex flex-col items-center">
          <QrCode value={verificationUri} size={QR_SIZE} alt="Ссылка для подтверждения устройства" />
          <div className="mt-4">Или наведите камеру телефона на QR-код</div>
        </div>
      </div>
    </>
  );
};

export default PairView;
