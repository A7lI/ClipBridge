export function setupPickers() {
  for (const button of document.querySelectorAll('[data-pick]')) button.addEventListener('click', () => {
    const input = document.getElementById(button.dataset.pick);
    if (!input.disabled) input.click();
  });
}

export function describeSelection(files, target) {
  target.textContent = files.length === 1 ? files[0].name : `${files.length} files · ${(files.reduce((sum, file) => sum + file.size, 0) / 1024 / 1024).toFixed(1)} MB`;
  target.title = files.map(file => file.name).join('\n');
}
