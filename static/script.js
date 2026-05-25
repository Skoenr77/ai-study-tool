let selectedFile = null;

async function generate() {
    const notes = document.getElementById("notes").value;
    const mode = document.getElementById("mode").value;
    const language = document.getElementById("language").value;
    const resultBox = document.getElementById("result-box");
    const progress = document.getElementById("progressFill");

    resultBox.innerText = "Generating...";
    progress.style.width = "20%";

    try {
        // FILE MODE
        if (selectedFile) {
            const formData = new FormData();
            formData.append("file", selectedFile);
            formData.append("mode", mode);
            formData.append("language", language);

            const response = await fetch("/upload-process", {
                method: "POST",
                body: formData
            });

            const data = await response.json();

            progress.style.width = "100%";
            resultBox.innerText = data.result || "Error processing file";
            return;
        }

        // TEXT MODE
        if (!notes.trim()) {
            alert("Please enter notes or choose a file first");
            return;
        }

        const response = await fetch("/summarize", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                notes: notes,
                mode: mode,
                language: language
            })
        });

        progress.style.width = "80%";

        const data = await response.json();

        resultBox.innerText = data.result || "Error generating result";
        progress.style.width = "100%";

    } catch (error) {
        resultBox.innerText = "Connection error";
        console.error(error);
    }
}


// FILE PICKER
document.getElementById("fileInput").addEventListener("change", function(event) {
    const file = event.target.files[0];

    if (!file) return;

    selectedFile = file;

    document.getElementById("notes").value =
        "Selected file: " + file.name + " (" + Math.round(file.size / 1024) + " KB)";
});


function copyResult() {
    navigator.clipboard.writeText(
        document.getElementById("result-box").innerText
    );
}


function downloadPDF() {
    window.print();
}


function speakResult() {
    const text = document.getElementById("result-box").innerText;

    if (!text.trim()) return;

    const speech = new SpeechSynthesisUtterance(text);

    speech.lang =
        document.getElementById("language").value === "arabic"
            ? "ar-SA"
            : "en-US";

    window.speechSynthesis.speak(speech);
}


function stopSpeech() {
    window.speechSynthesis.cancel();
}


function toggleDarkMode() {
    document.body.classList.toggle("dark-mode");
}