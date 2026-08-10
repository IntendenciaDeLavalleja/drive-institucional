document.addEventListener("click", (event) => {
  const open = event.target.closest("[data-dialog-open]");
  if (open) document.getElementById(open.dataset.dialogOpen)?.showModal();
  if (event.target.closest(".dialog-close")) event.target.closest("dialog")?.close();
  const copy = event.target.closest("[data-copy]");
  if (copy) {
    const field = document.querySelector(copy.dataset.copy);
    navigator.clipboard.writeText(field.value).then(() => {
      copy.textContent = "Copiado";
      setTimeout(() => copy.textContent = "Copiar", 1800);
    });
  }
});

document.querySelectorAll("form[data-confirm]").forEach((form) => {
  form.addEventListener("submit", (event) => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  });
});

document.querySelectorAll(".upload-form").forEach((form) => {
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const progress = form.querySelector(".upload-progress");
    const bar = progress.querySelector("div");
    const label = progress.querySelector("span");
    progress.hidden = false;
    form.querySelector("button[type=submit]").disabled = true;
    const xhr = new XMLHttpRequest();
    xhr.open("POST", form.action);
    xhr.upload.addEventListener("progress", (e) => {
      if (!e.lengthComputable) return;
      const pct = Math.round((e.loaded / e.total) * 100);
      bar.style.width = `${pct}%`;
      label.textContent = `Subiendo… ${pct}%`;
    });
    xhr.addEventListener("load", () => {
      if (xhr.responseURL) window.location.assign(xhr.responseURL);
      else window.location.reload();
    });
    xhr.addEventListener("error", () => {
      label.textContent = "La carga falló. Intentá nuevamente.";
      form.querySelector("button[type=submit]").disabled = false;
    });
    xhr.send(new FormData(form));
  });
});

document.querySelectorAll("form[data-user-form]").forEach((form) => {
  const role = form.querySelector("[data-role-select]");
  const unitField = form.querySelector("[data-unit-field]");
  const unit = form.querySelector("[data-unit-select]");
  const syncUnitField = () => {
    const isAdmin = role.value === "admin";
    unitField.hidden = !isAdmin;
    unit.disabled = !isAdmin;
    unit.required = isAdmin;
    if (!isAdmin) unit.value = "";
  };
  role.addEventListener("change", syncUnitField);
  syncUnitField();
});
