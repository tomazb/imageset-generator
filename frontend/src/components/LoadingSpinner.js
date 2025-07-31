import React from 'react';
import './LoadingSpinner.css';

const LoadingSpinner = ({ size = 'small', inline = false }) => {
  const className = `loading-spinner ${size} ${inline ? 'inline' : ''}`;
  
  return (
    <div className={className}>
      <div className="spinner"></div>
    </div>
  );
};

export default LoadingSpinner;
