import React from 'react';
import { CalibrationPreview } from '../components/CalibrationPreview';

export const Calibration: React.FC = () => {
  // Get server IP from current location
  const serverIp = window.location.hostname;

  return <CalibrationPreview serverIp={serverIp} />;
};
