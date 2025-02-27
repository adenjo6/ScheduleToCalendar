import React, { useRef } from 'react';

const FileUploadComponent = ({ onFileChange }) => {
  const ref = useRef();

  const handleClick = () => {
    ref.current.click();
  };

  return (
    <>
      <button onClick={handleClick}>Upload Image</button>
      <input
        ref={ref}
        type="file"
        style={{ display: 'none' }}
        accept="image/*"
        onChange={onFileChange}
      />
    </>
  );
};

export default FileUploadComponent;