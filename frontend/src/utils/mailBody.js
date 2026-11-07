/**
 * Отделяет новый текст письма от цитаты ответа и подписи,
 * чтобы не засорять переписку в UI.
 */
export function splitMailBody(body) {
  if (!body) return { main: "", rest: "" };

  const lines = String(body).replace(/\r\n/g, "\n").split("\n");
  let cut = lines.length;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    // RFC 3676 signature delimiter
    if (trimmed === "--" || trimmed === "-- ") {
      cut = i;
      break;
    }

    // Quoted reply lines (possibly indented)
    if (/^\s*>/.test(line)) {
      cut = i;
      while (cut > 0 && !lines[cut - 1].trim()) cut -= 1;
      break;
    }

    // Common reply headers (EN / RU / Mail.ru style without leading >)
    if (
      /^(On\s.+wrote:|Am\s.+schrieb\s|Le\s.+a écrit|El\s.+escribió)/i.test(trimmed) ||
      /\d{1,2}[:.]\d{2}.+\sот\s+.+:\s*$/i.test(trimmed) ||
      /^From:\s*.+/i.test(trimmed) ||
      (/^От:\s*.+/i.test(trimmed) && i > 0)
    ) {
      cut = i;
      while (cut > 0 && !lines[cut - 1].trim()) cut -= 1;
      break;
    }
  }

  let mainLines = lines.slice(0, cut);
  const restLines = lines.slice(cut);

  // Mobile mail client footers that sometimes sit above `--`
  while (mainLines.length) {
    const last = mainLines[mainLines.length - 1].trim();
    if (
      !last ||
      /^Отправлено из Почты/i.test(last) ||
      /^Sent from my /i.test(last) ||
      /^Get Outlook for /i.test(last)
    ) {
      mainLines.pop();
      continue;
    }
    break;
  }

  const main = mainLines.join("\n").trim();
  const rest = restLines.join("\n").trim();
  // If stripping removed everything, show original
  if (!main && body.trim()) {
    return { main: body.trim(), rest: "" };
  }
  return { main, rest };
}
