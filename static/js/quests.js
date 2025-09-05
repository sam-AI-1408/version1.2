// quests.js

document.addEventListener("DOMContentLoaded", () => {
  const periodButtons = document.querySelectorAll(".quest-tabs button");
  const questsBoard = document.getElementById("questsBoard");
  const pointsEl = document.getElementById("points-display"); // Use consistent element

  let activePeriod = "daily";

  // --- Helper functions ---
  function formatQuestCard(q) {
    return `
      <div class="quest-card" id="quest-${q.id}">
        <h3>${q.title}</h3>
        <p><em>${q.category.toUpperCase()}</em></p>
        ${q.type === "online" && q.link ? `<p><a href="${q.link}" target="_blank">📘 Resource</a></p>` : ""}
        <div class="quest-controls">
          ${q.completed 
            ? `<span style="color:lime">✔ Completed</span>` 
            : `<button class="complete-btn" data-id="${q.id}">✅ Complete (+${q.xp} XP)</button>`}
        </div>
      </div>
    `;
  }

  async function fetchQuests(period) {
    try {
      const resp = await fetch(`/get_user_quests?period=${period}`);
      if (!resp.ok) throw new Error("Failed to fetch quests.");
      const data = await resp.json();
      return data;
    } catch (err) {
      console.error(err);
      questsBoard.innerHTML = `<div class="quest-card"><h3>Error loading quests.</h3></div>`;
      return [];
    }
  }

  async function completeQuest(questId, btn) {
    try {
      btn.disabled = true; // disable button while processing
      const resp = await fetch("/complete_quest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ quest_id: questId }),
        credentials: "include" // ensures session cookie is sent
      });
      const data = await resp.json();

      if (data.success) {
        pointsEl.innerText = data.points;
        btn.outerHTML = `<span style="color:lime">✔ Completed</span>`;
      } else {
        alert(data.error || "Failed to complete quest.");
        btn.disabled = false;
      }
    } catch (err) {
      console.error(err);
      alert("Network error. Please try again.");
      btn.disabled = false;
    }
  }

  async function loadQuests(period) {
    const quests = await fetchQuests(period);
    questsBoard.innerHTML = "";

    if (!quests.length) {
      questsBoard.innerHTML = `<div class="quest-card"><h3>No quests available.</h3></div>`;
      return;
    }

    quests.forEach(q => {
      questsBoard.innerHTML += formatQuestCard(q);
    });

    // Add event listeners to complete buttons
    document.querySelectorAll(".complete-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const questId = btn.dataset.id;
        completeQuest(questId, btn);
      });
    });
  }

  // --- Tab button click ---
  periodButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      periodButtons.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      activePeriod = btn.dataset.type;
      loadQuests(activePeriod);
    });
  });

  // --- Initialize ---
  const activeBtn = document.querySelector(".quest-tabs button.active") || periodButtons[0];
  if (activeBtn) {
    activeBtn.classList.add("active");
    activePeriod = activeBtn.dataset.type;
    loadQuests(activePeriod);
  }
});

fetch("/complete_quest", {
  method: "POST",
  headers: {"Content-Type": "application/json"},
  body: JSON.stringify({ quest_id: questId }),
  credentials: "include"
})

document.querySelectorAll(".complete-quest-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
        const questId = btn.dataset.questId;

        const res = await fetch("/complete_quest", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ quest_id: questId })
        });

        const data = await res.json();
        if(data.success){
            // Mark the quest visually as completed
            const questElem = document.getElementById(`quest-${questId}`);
            if(questElem){
                questElem.classList.add("completed");  // Add a CSS class like .completed { opacity: 0.5; text-decoration: line-through; }
                btn.disabled = true;
                btn.textContent = "Completed";
            }

            // Update points dynamically
            const pointsElem = document.getElementById("points-display");
            if(pointsElem){
                pointsElem.textContent = data.points;
            }
        } else {
            alert(data.error || "Failed to complete quest.");
        }
    });
});
