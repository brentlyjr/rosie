

class Passage {
    constructor(filename = null, text = "", language = "english") {
      this.audioSnippet = new AudioSnippet(filename, language);
      this.isRecording = false;
      // this.textSnippet = new TextSnippet(text, language);
      this.language = language;
    }
  
    playAudio() {
      this.audioSnippet.playAudio();
    }
  
    async recordAudio(duration = 5) {
      await this.audioSnippet.recordAudio(duration);
    }
  
    getText() {
      return this.textSnippet.getText();
    }
  
    addText(text) {
      this.textSnippet.addText(text);
    }
  
    async translateToText() {
      const text = await this.audioSnippet.translateToText();
      this.textSnippet = new TextSnippet(text, this.language);
    }
  
    async translateToSpeech() {
      const file = await this.textSnippet.translateToSpeech();
      this.audioSnippet.addAudio(file);
    }

    async playAudioWithButtonFeedback(button) {
        button.style.backgroundColor = '#45a049';
        const playingText = document.createElement('p');
        playingText.textContent = 'Playing sound';
        button.insertAdjacentElement('afterend', playingText);
    
        await this.playAudio();
    
        playingText.remove();
        button.style.backgroundColor = '#4CAF50';
  }

  async recordAudioWithButtonFeedback(button, duration) {
    if (!this.isRecording) {
      button.style.backgroundColor = "#FF5722";
      const recordingText = document.createElement("p");
      recordingText.textContent = "Recording in progress";
      button.insertAdjacentElement("afterend", recordingText);
      this.recordingText = recordingText;

      this.isRecording = true;
      await this.recordAudio(duration);
    } else {
      this.mediaRecorder.addEventListener("stop", () => {
        this.isRecording = false;
        button.style.backgroundColor = "#4CAF50";
        this.recordingText.remove();
      });
      this.mediaRecorder.stop();
    }
  }
}
  
class AudioSnippet {
    constructor(language = "english") {
        this.language = language;
        this.mediaRecorder = null;
        this.audioChunks = [];
    }

    async playAudio() {
        if (this.audioChunks.length === 0) {
        console.error("No audio data to play.");
        return;
        }

        const audioBlob = new Blob(this.audioChunks, { type: "audio/webm" });
        const audioUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio(audioUrl);
        await audio.play();
    }

    async recordAudio(duration) {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        console.error("getUserMedia not supported in this browser.");
        return;
        }

        try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        this.mediaRecorder = new MediaRecorder(stream);
        this.audioChunks = [];

        this.mediaRecorder.addEventListener("dataavailable", (event) => {
            this.audioChunks.push(event.data);
        });

        this.mediaRecorder.start();

        setTimeout(() => {
            this.mediaRecorder.stop();
        }, duration * 1000);
        } catch (error) {
        console.error("Error while recording:", error);
        }
    }
}
// Create a new Passage instance

// Create a new Passage instance
const passage = new Passage();

// Attach event listeners to the buttons
const recordButton = document.getElementById('recordButton');
const playButton = document.getElementById('playButton');

recordButton.addEventListener("click", () =>
  passage.recordAudioWithButtonFeedback(recordButton, 5)
);

playButton.addEventListener('click', () => passage.playAudioWithButtonFeedback(playButton));