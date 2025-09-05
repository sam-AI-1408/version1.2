// =======================
// Sam AI Professional Voice Assistant
// =======================

// Assistant state
let recognition;
let assistantActive = false;
let username = window.username || "Player"; // set in HTML by Flask template

// UI Elements
const micBtn = document.createElement("button");
micBtn.id = "sam-voice-btn";
micBtn.innerHTML = "🎤";
Object.assign(micBtn.style, {
  position: "fixed",
  bottom: "25px",
  right: "25px",
  width: "60px",
  height: "60px",
  borderRadius: "50%",
  border: "none",
  backgroundColor: "#00d0ff",
  color: "#050615",
  fontSize: "28px",
  cursor: "pointer",
  boxShadow: "0 4px 15px rgba(0,0,0,0.3)",
  zIndex: "9999",
});
document.body.appendChild(micBtn);

const feedback = document.createElement("div");
feedback.id = "sam-voice-feedback";
Object.assign(feedback.style, {
  position: "fixed",
  bottom: "95px",
  right: "25px",
  background: "#0f1630",
  color: "#00d0ff",
  padding: "10px 16px",
  borderRadius: "12px",
  boxShadow: "0 4px 20px rgba(0,0,0,0.5)",
  fontFamily: "Arial, sans-serif",
  fontSize: "14px",
  maxWidth: "250px",
  display: "none",
});
document.body.appendChild(feedback);

// --- Speech setup ---
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
recognition = new SpeechRecognition();
recognition.lang = "en-US";
recognition.interimResults = false;
recognition.maxAlternatives = 1;

// --- Speak function ---
function speak(text) {
  const utter = new SpeechSynthesisUtterance(text);
  utter.lang = "en-US";
  utter.rate = 1;
  utter.pitch = 1;
  speechSynthesis.speak(utter);
}

// --- Core command processor ---
async function processCommand(command) {
  command = command.toLowerCase();
  let response = "";

  // ========== Wake Word ==========
  if (!assistantActive) {
    if (command.includes("arise")) {
      assistantActive = true;
      response = `Hi ${username}, how was your day?`;
    } else {
      response = `Say "Arise" to activate me.`;
    }
    feedback.innerText = response;
    feedback.style.display = "block";
    speak(response);
    return;
  }

  // ========== Small Talk ==========
  if (command.includes("nice") || command.includes("good")) {
    response = `Glad to hear that, ${username}. Did anything go wrong today?`;
  } else if (command.includes("nothing") || command.includes("no")) {
    response = `Okay, ${username}, let me tell you today’s quests.`;
    // Example fetch (must exist in Flask)
    try {
      const res = await fetch("/get_todays_quests");
      const data = await res.json();
      response = "Today's quests are " + data.quests.join(", ");
    } catch {
      response = "I couldn’t fetch today’s quests.";
    }
  }

  // ========== Commands ==========
  // Tasks
  else if (command.includes("add task")) {
    const title = command.replace("add task", "").trim();
    if (title) {
      await fetch("/add_task", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: `title=${encodeURIComponent(title)}`
      });
      response = `Task '${title}' added.`;
    } else response = "Please tell me the task name.";
  }
  else if (command.includes("complete task")) {
    const id = command.match(/\d+/);
    if (id) {
      const res = await fetch(`/complete_task/${id[0]}`, { method: "POST" });
      const data = await res.json();
      response = data.success ? `Task ${id[0]} completed.` : "Failed to complete task.";
    } else response = "Please specify the task ID.";
  }
  else if (command.includes("delete task")) {
    const id = command.match(/\d+/);
    if (id) {
      await fetch(`/delete_task/${id[0]}`, { method: "POST" });
      response = `Task ${id[0]} deleted.`;
    } else response = "Please specify the task ID to delete.";
  }
  else if (command.includes("open tasks")) {
    window.location.href = "/tasks";
    response = "Opening tasks.";
  }

  // Academics
  else if (command.includes("open academics")) {
    window.location.href = "/academics";
    response = "Opening academics.";
  }
  else if (command.includes("start session")) {
    response = "Study session started.";
  }
  else if (command.includes("add notes")) {
    response = "You can now add notes manually in academics.";
  }
  else if (command.includes("start timer")) {
    const mins = command.match(/\d+/);
    if (mins) {
      response = `Timer started for ${mins[0]} minutes.`;
      setTimeout(() => {
        feedback.innerText = "Timer completed!";
        speak("Timer completed!");
      }, mins[0] * 60000);
    } else response = "Please specify a duration in minutes.";
  }

  // Quests
  else if (command.includes("open quests")) {
    window.location.href = "/quests";
    response = "Opening quests.";
  }
  else if (command.includes("today's quests")) {
    try {
      const res = await fetch("/get_todays_quests");
      const data = await res.json();
      response = "Today's quests are " + data.quests.join(", ");
    } catch {
      response = "I couldn’t fetch today’s quests.";
    }
  }
  else if (command.includes("complete daily quest")) {
    await fetch("/complete_today_quest", { method: "POST" });
    response = "Daily quest completed.";
  }

  // Profile
  else if (command.includes("show username")) {
    response = `Your username is ${username}.`;
  }
  else if (command.includes("show points")) {
    const el = document.getElementById("points");
    response = `You have ${el ? el.textContent : "0"} points.`;
  }
  else if (command.includes("show rank")) {
    const el = document.getElementById("rank");
    response = `Your rank is ${el ? el.textContent : "Bronze"}.`;
  }
  else if (command.includes("show stats")) {
    response = "Your stats are visible in the profile page.";
  }
  else if (command.includes("show quote")) {
    const el = document.getElementById("quote");
    response = el ? el.textContent : "No quote set.";
  }
  else if (command.includes("edit profile")) {
    window.location.href = "/profile";
    response = "Opening profile editor.";
  }
  else if (command.includes("open developer")) {
    window.location.href = "/developer";
    response = "Opening developer profile.";
  }

  // Command Help
  else if (command.includes("command")) {
    response = "You can say: add task, complete task, delete task, open tasks, open academics, start session, start timer, add notes, open quests, complete daily quest, today's quests, show points, show rank, show stats, show username, show quote, edit profile, open developer, or terminate to close me.";
  }

  // Terminate
  else if (command.includes("terminate") || command.includes("close")) {
    assistantActive = false;
    response = "Voice assistant closed.";
  }

  // Unknown
  else {
    response = "Sorry, I didn’t understand that command.";
  }

  // --- Output ---
  feedback.innerText = response;
  feedback.style.display = "block";
  speak(response);
}

// --- Recognition Start ---
micBtn.addEventListener("click", () => {
  feedback.style.display = "block";
  feedback.innerText = "Listening...";
  recognition.start();
});

recognition.onresult = (event) => {
  const command = event.results[0][0].transcript;
  feedback.innerText = `You said: "${command}"`;
  processCommand(command);
};

recognition.onerror = (event) => {
  feedback.innerText = "Error: " + event.error;
  speak("Sorry, I could not hear you clearly. Try again.");
};
