# Konzept: Mehr-Parteien-Debatten (Multi-Party)

Status: Entwurf / Designdokument
Betrifft beide Repos: `fair-debate-md` (Backend, Key-System) und `fair-debate-web` (Frontend, Datenmodell + UI).

## 1. Ziel

Heute kann an einer Debatte nur **genau zwei** Parteien teilnehmen (Rollen `a` und `b`).
Ziel: eine Debatte für **beliebig viele** Teilnehmer öffnen, ohne das Transparenz- und
Fairness-Versprechen des Konzepts (`fair-debate-web/konzept.md`) aufzugeben.

## 2. Getroffene Entscheidungen

Referenzen verweisen auf die Diskussionsfragen, in denen die Entscheidung fiel.

- **Identitätsmodell (Q1a):** "Ad hoc, ungedeckelt". Jede neue antwortende Person wird
  automatisch eine neue Einzel-Partei. Gruppen (mehrere Personen pro Partei) sind bewusst
  vertagt.
- **Antwort-Topologie (Q2a):** Ein Segment darf **mehrere** direkte Antworten erhalten
  (`a5b`, `a5c`, `a5d`, …) — von *verschiedenen* Parteien.
- **Key-Bedeutung (Q3b, Modell X):** Der Token im Key **identifiziert die Partei**, nicht nur
  einen Geschwister-Index. Maximale Transparenz: aus dem Key ist ablesbar, von welcher Partei
  ein Statement stammt.
- **Token-Geltungsbereich (Klarstellung):** Tokens gelten **pro Debatte**, nicht global.
  Ein User kann in Debatte 1 Token `b` und in Debatte 2 Token `f` haben. Für N globale User
  braucht es **nicht** N Tokens, sondern nur so viele, wie *in einer einzelnen Debatte*
  teilnehmen. Erschöpfung tritt erst bei >26 Parteien *in derselben Debatte* ein → dann
  mehrstellige Tokens (`aa`, `ab`, …).
- **Sortierung (Q4):** v1 chronologisch, älteste zuerst. Später umstellbar (Sortier-Option).
- **Repo-/Git-Modell (Q6a):** v1 weiterhin **ein** Repo pro Debatte, Unterordner pro Token
  (`a/`, `b/`, `c/`, …). Multi-Remote-/Fork-/Repo-pro-Partei-Story bewusst vertagt.
- **Antworten pro Partei/Segment (Q7a + ii):** Eine Partei hat **höchstens eine** direkte
  Antwort pro Segment (editierbar), da `Segment + Token` eindeutig ist. Eine Partei **darf**
  ihr eigenes Segment beantworten (`a5a`; Nachtrag/Selbstkommentar erlaubt).
- **Sichtbarkeitsfilter (Q9a):** rein **clientseitig**, pro Betrachter (JS-Toggle; alle Daten
  sind ohnehin öffentlich). v1 Blacklist (alle sichtbar außer ausgeblendeten), später optional
  Whitelist.
- **Partei-Beschriftung (Q10b):** Username + Repo-Link, falls Repo-Link verfügbar, sonst nur
  Username.

### Bestätigte Annahme

- **Annahme A1 (Q8, Ereignisprotokoll) — bestätigt:** v1 nutzt DB-Zeitstempel
  (`created`/`updated` auf `Contribution`); die Veröffentlichungszeit kommt für committete
  Beiträge aus der Git-Commit-Zeit. Das volle Doppel-Ereignis-Log (Entwurf erzeugt /
  veröffentlicht getrennt) ist eine spätere Verfeinerung.

## 3. Key-Schema (Modell X)

Ein Key kodiert den **Pfad im Debatten-Baum**; jeder Token ist eine Partei-Kennung,
jede Zahl ein Segment-Index innerhalb eines Beitrags.

Beispiel `a5c3b`:
- `a`  Eröffnungs-Beitrag von Partei a
- `5`  Segment 5 darin
- `c`  Partei c antwortet auf `a5`
- `3`  Segment 3 in der Antwort von c
- `b`  Partei b antwortet auf `a5c3`

Eigenschaften:
- Der **Wurzel-Token ist immer `a`** (Eröffner der Debatte).
- Der Kind-Key ergibt sich aus **Eltern-Segment + Token des Antwortenden** —
  *nicht* mehr aus einem `a↔b`-Flip.
- `Segment + Token` ist eindeutig → eine Partei hat max. eine direkte Antwort pro Segment.
- Token-Vergabe: bei **erster Teilnahme** einer Partei in einer Debatte wird der nächste
  freie Token vergeben (`a`, `b`, …, `z`, `aa`, `ab`, …).

## 4. Datenmodell (`fair-debate-web/base/models.py`)

### Neu: `DebateParticipant` (Through-Model)

Ersetzt die festen Slots `user_a/user_b` und `repo_a/repo_b` am `Debate`-Model.

```
class DebateParticipant(models.Model):
    debate = ForeignKey(Debate)
    user   = ForeignKey(DebateUser)
    token  = CharField        # "a", "b", ..., "aa", ... ; pro Debatte eindeutig
    repo   = ForeignKey(Repo, null=True)   # optional, für Repo-Link in der UI
    # unique_together: (debate, user) und (debate, token)
```

- `Debate.user_a/user_b/repo_a/repo_b` entfallen.
- `Debate.get_user_role(user)` → gibt den Token der Partei zurück (oder None).
- `Debate.get_for_user(...)` → Query über `DebateParticipant` statt über user_a/user_b.
- Token-Allokator: Hilfsfunktion "nächster freier Token in dieser Debatte".

### `Contribution`: Zeitstempel ergänzen (Annahme A1)

```
created = models.DateTimeField(auto_now_add=True)
updated = models.DateTimeField(auto_now=True)
```

(Für das optional einblendbare Ereignisprotokoll.)

## 5. Backend-Änderungen (`fair-debate-md/src/fair_debate_md/`)

Zentrale, gut abgegrenzte Stellen — das Key-System ist das Fundament.

- `core.py:357` `key_regex = r"[ab]\d+"` → `r"[a-z]+\d+"` (mehrstellige Tokens erlaubt).
  `decompose_key` bleibt strukturell gleich (Buchstaben-Lauf / Ziffern-Lauf).
- `core.py:539` `get_next_turn_key(segment_key)` (a↔b-Flip) **entfällt** bzw. wird ersetzt:
  Der nächste Token ergibt sich aus dem **Antwortenden**, nicht aus dem Eltern-Key.
- `core.py:531` `get_contribution_key(segment_key)` → bekommt zusätzlich den
  **Antwortenden-Token**: `get_contribution_key(segment_key, answering_token)`.
- `core.py:503-528` `generate_html_with_contributions`: bisher genau **ein** Kind pro
  Segment (`contribution_key = f"{key}{next_turn_key}"`). Künftig **alle** Kinder sammeln,
  die zu `{key}{beliebiger_token}` passen → `contribution_childs[key]` wird eine **Liste**,
  Reihenfolge = chronologisch (älteste zuerst, v1).
- `core.py:410-411` `dir_a`, `dir_b` → dynamische Verzeichnisse pro Token (`a/`, `b/`, `c/`…).
  `load_dir` (`core.py:437-438`) globbt entsprechend alle Token-Verzeichnisse.
- `core.py:464` `self.root_mdp = self.tree["a"]` bleibt (Wurzel ist Token `a`).
- `core.py:611-628` `write_ctb_to_file`: `author_role = ctb_key[-1]` → letzter **Token**
  (nicht zwingend einstellig); `assert in [a,b]` entfällt; Zielverzeichnis = Token.
- `core.py:607` / `repo_handling.py:59` `get_author(debate_key, author_role)`:
  Rollen-Argument wird zum Token verallgemeinert.
- `md_handling.py:63` `key_prefix="a"` (Wurzel) bleibt.

## 6. Frontend-Änderungen (`fair-debate-web/base/`)

- `views.py:88` `NewDebateView.post`: statt `user_a=request.user` einen
  `DebateParticipant`-Eintrag mit Token `a` anlegen.
- `views.py:313-314` `contribution_mode = contribution_key[-1]; assert in (a,b)`:
  Mode = letzter Token; Assertion entfernen/verallgemeinern.
- `views.py:312` Kind-Key künftig aus Segment + Token des aktuellen Users.
- `views.py:355` `_ensure_suitable_user_role`: Logik "wer Rolle b greifen darf" →
  "User ist bereits Partei (nutzt seinen Token)" **oder** "neuer User → nächster freier
  Token wird vergeben". Eine Partei darf ihr eigenes Segment beantworten (Q7-ii).
- `views.py:405-423` `render_result_from_html`: `user_b == "__undefined__"`-Sonderfall →
  Teilnehmer-Liste (Token → User/Repo) in den Context geben.
- Templates (`main_show_debate.html`, `partials/debate_list_entry.html`): Rollen-Anzeige
  verallgemeinern; pro Partei Username + Repo-Link (Q10b).
- `static/core.js:86-87,165,213,433-438`: Antwort-Routing und Hinweise sind an die Rollen
  `a`/`b` und `user_b` gebunden → auf beliebige Tokens + Teilnehmer-Liste umstellen.

## 7. Darstellung

- **Grundprinzip (bewusst schlicht):** Die Debatte ist logisch ein Baum (Segment → Antworten
  → deren Segmente → …), aber das war auch mit zwei Parteien schon so. Optisch bleibt es bei
  dem bewährten Bild: Antworten stehen **klar getrennt untereinander** unter dem jeweiligen
  Segment. Kein neues, schwergewichtiges Tree-Widget nötig.
- **Einzig Neues:** Ein Segment kann **mehrere** direkte Antworten haben → diese erscheinen als
  mehrere klar abgegrenzte Antwort-Blöcke untereinander, **jeder mit Partei-Beschriftung**
  (Token + Username, Klartext-Identität aus Teilnehmer-Liste). Die Verschachtelungstiefe
  (Antwort auf Antwort) funktioniert wie bisher.
- **Optional/später:** Ein-/Ausklappen sehr voller Segmente, stärkere Einrückung pro Ebene —
  nur falls sich in Tests Unübersichtlichkeit zeigt.
- **Sortierung:** Geschwister-Antworten chronologisch, älteste zuerst (v1). Sortier-Option
  später.
- **Ereignisprotokoll:** optional einblendbar; pro Contribution Zeitstempel.
- **Sichtbarkeitsfilter:** clientseitiger Toggle pro Betrachter; v1 Blacklist.

## 8. Migration bestehender Debatten

Bestehende a/b-Debatten sind unter Modell X bereits gültig: `a` und `b` sind schlicht die
ersten beiden Tokens. Daten-Migration:
- `Debate.user_a` → `DebateParticipant(token="a")`
- `Debate.user_b` → `DebateParticipant(token="b")` (falls gesetzt)
- `repo_a/repo_b` → `participant.repo`

Risiko gering; die Verzeichnisstruktur `a/`, `b/` bleibt kompatibel.

## 9. Phasen

0. **Designdokument** (dieses Dokument) — bestätigen.
1. **Backend-Keys:** Regex weiten, `get_contribution_key(seg, token)`, mehrere Kinder pro
   Segment, Token-Verzeichnisse, `write_ctb_to_file`/`get_author` verallgemeinern.
   Testintensiv (Fundament). Bestehende Tests müssen grün bleiben.
2. **Frontend-Datenmodell:** `DebateParticipant` Through-Model + Migration, `Contribution`
   Zeitstempel, Queries (`get_user_role`, `get_for_user`) anpassen.
3. **Frontend-Logik:** Token-Vergabe, Antwort-Routing, `_ensure_suitable_user_role`,
   Context/Teilnehmer-Liste.
4. **Frontend-UX:** Baum-Darstellung, Autor-Anzeige, Sortierung, Ereignisprotokoll,
   Sichtbarkeitsfilter.

## 10. Bewusst vertagt

- Gruppen (mehrere Personen pro Partei).
- Repo-pro-Partei mit eigenen Remotes / Fork-Workflow.
- Voting / Reputation / Whitelist-Sichtbarkeit / umstellbare Sortierung.
- Volles Doppel-Ereignis-Log (Entwurf vs. Veröffentlichung).
