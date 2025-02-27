import React, { useState } from 'react';
import axios from 'axios';
import './App.css';
import FileUploadComponent from './Button';

function App() {
  const [message, setMessage] = useState('');
  const [scheduleImg, setScheduleImg] = useState(null);
  const [scheduleImgURL, setScheduleImgURL] = useState(null);  // State for image URL

  console.log("scheduleImg:", scheduleImg); //for debugging, console.log helps inspect values

  /*
    1. Create Form Data: Append the uploaded image to formData.
    2. Send POST Request: Use Axios to send the form data to the backend endpoint.
    3. Handle Response: Download the ICS file from the response.
    4. Catch Errors: Log any errors that occur during the request.
  */
  const processSchedule = async () => { //sending frontend input of schedule img to the backend
    if (!scheduleImg) {                                                                                                                                                                                                                                                                                                                                                                                                                                                         
      setMessage('Please upload an image first.');
      return;
    }

    const formData = new FormData(); //Purpose of formdata is to facilitate the submission of form data, like files, through HTTP requests
    formData.append('image', scheduleImg); // Changed key to 'image'

    try {
      const response = await axios.post(`${process.env.REACT_APP_API_BASE_URL}/upload-schedule`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        },
        responseType: 'blob' // Expect binary data for ICS file
      });

      // Create a URL for the blob data
      const url = window.URL.createObjectURL(new Blob([response.data], { type: 'text/calendar' }));

      // Create a temporary link element
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'schedule.ics'); // Set the download attribute with a default filename

      // Append the link to the document body and trigger a click to start download
      document.body.appendChild(link);
      link.click();

      // Cleanup: Remove the link and revoke the object URL
      link.parentNode.removeChild(link);
      window.URL.revokeObjectURL(url);

      // Inform the user about the successful download
      setMessage('ICS file downloaded successfully!');
    }
    catch (error) {
      console.error('Error processing the schedule:', error);
      setMessage('Failed to process the schedule. Please try again.');
    }
  };

  const handleFileChange = (event) => {
    const file = event.target.files[0];
    console.log("Selected file:", file); // Debugging line
    setScheduleImg(file);
    setScheduleImgURL(URL.createObjectURL(file));  // Create and set URL
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>Schedule to Calendar</h1>
        <div className="upload-section">
          <p>Upload your schedule</p>
          <FileUploadComponent onFileChange={handleFileChange} />
        </div>
        {scheduleImgURL && <img src={scheduleImgURL} className="imageSchedule" alt="Uploaded Schedule" />}

        <button onClick={processSchedule}>Process your Schedule!</button>
        <p className="message">{message}</p>
      </header>
    </div>
  );
}

export default App;