Passage 
    contains 
        AudioSnippet 
        TextSnippet

    Methods 
        play_audio 
        record_audio 
        get_text 
        add_text 
        get_audiosnippet 
        get_textsnippet 
        translate_text_to_speech 
        translate_speech_to_text

AudioSnippet 
    contains SpeechRecognizer

    Methods 
        play_audio 
        record_audio 
        translate_to_text 
        get_file

TextSnippet 
    contains 
        SpeechSynthesizer
    
    Methods 
        get_text
        add_text 
        translate_text_to_speech


SpeechSynthesizer 
    Methods 
    translate_text_to_speech

SpeechRecognizer 
    Methods 
        translate_to_text