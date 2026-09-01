---
debate_key: d01-erklaerende-beispieldebatte
language: de
parties:
  a: Erklärer
  b: Ergänzer
  c: Fragesteller
first_commit: 2026-08-24T09:00:00+02:00
hours_between_contributions: [4, 8]
active_hours: [8, 22]
---

<!-- !!== label=root party=a ==== -->

# Erklärende Beispiel-Debatte

Dieses Dokument ist eine *Debatte*. Es beschreibt die wichtigsten Eigenschaften von *Fair Debate* — der Plattform, die du gerade vor dir hast — und begründet sie. Dabei zweckentfremdet es die Funktionen der Plattform, nämlich die besondere Darstellung von Rede und Gegenrede, für Erklärungen. Eigentlich ist Fair Debate nicht dafür gedacht, Dokumentation anzuzeigen, sondern als Werkzeug für sachliche und nachvollziehbare Verständigung über womöglich strittige Themen.

Du liest gerade den eröffnenden *Beitrag* dieser Debatte. Er trägt den Beitragsschlüssel `a`. Jeder Beitrag wird automatisch in *Segmente* zerlegt — Überschriften, Sätze, Aufzählungspunkte. Die Segmente eines Beitrags bekommen eigene Schlüssel wie `a1`, `a2` und so weiter. Dadurch lässt sich jedes Segment genau benennen. Und jedes Segment lässt sich einzeln beantworten. Wenn du mit der Maus über ein Segment fährst, siehst du seinen Schlüssel; ein Klick oder Fingertipp erlaubt dir außerdem, seine URL zu kopieren und darauf zu antworten.

Hervorgehobene Segmente sind bereits beantwortet worden. Klicke auf ein solches Segment, um die Antworten darunter aufzuklappen. Der größte Teil dieses Dokuments steckt in diesen Antworten, Aufklappen ist also die Art, es zu lesen.

An einer Debatte können mehrere Parteien (Benutzerkonten) teilnehmen. Parteien werden durch Buchstaben bezeichnet, vergeben in der Reihenfolge des Beitritts.

- `a` ist die Partei, die die Debatte eröffnet, hier also ich.
- `b` ist die Partei, die als erste antwortet.
- `c` ist die Partei, die als zweite antwortet.
- Weitere Parteien setzen das Alphabet fort und darüber hinaus (siehe unten).

Eine Partei kann auch ein eigenes Segment beantworten. So lässt sich ein Nachtrag in die Debatte einbringen, ohne das bereits Veröffentlichte umzuschreiben.

Zwei Eigenschaften unterscheiden diese Plattform von einem gewöhnlichen Kommentarbereich oder Forum. Sie werden in den Antworten erklärt.

1. Dauerhafte Antworten im Kontext.
2. Beweisbare Integrität der Inhalte.

Wenn du diese beiden Eigenschaften verstanden hast, kannst du Fair Debate schon recht gut benutzen. Es gibt allerdings noch einige Einzelheiten, die dich interessieren könnten.

## Häufige Fragen

Jede dieser Fragen wird weiter unten in einer eigenen Antwort behandelt — was zugleich vorführt, was diese Plattform tut.

- Was passiert, wenn mehr Parteien an der Debatte teilnehmen, als das Alphabet Buchstaben hat?
- Können mehrere Segmente oder Teile von Segmenten beantwortet werden?
- Wie lässt sich die Integrität einer Debatte prüfen, also die Abwesenheit von Manipulation?
- Wie wird die Plattform moderiert?
- Wie sammelt das Projekt Rückmeldungen?
- Kann man das Projekt unterstützen?

<!-- !!== label=b-intro party=b answers="`b` ist die Partei, die als erste antwortet" ==== -->

Das bin ich. Meine Rolle in dieser Debatte ist es, Einzelheiten zu ergänzen.

<!-- !!== label=c-intro party=c answers="`c` ist die Partei, die als zweite antwortet" ==== -->

Und das bin ich. Ich stelle (mitunter kritische) Fragen und suche nach Schwachstellen. Übrigens geht hier etwas nicht auf. Der Eröffnungsbeitrag weiß bereits, dass es eine Partei `b` und eine Partei `c` geben wird, und spricht von uns, bevor eine von uns beiden ein Wort geschrieben hatte. Diese Debatte wurde also nicht geführt, sie wurde verfasst.

<!-- !!== label=a-chronology party=a answers="Diese Debatte wurde also nicht geführt, sie wurde verfasst" ==== -->

Das stimmt, und es gehört ausgesprochen. Der Eröffnungsbeitrag sagt schon ganz am Anfang, dass dieses Dokument die Funktionen der Plattform für Erklärungen zweckentfremdet, und genau hier zeigt sich das. Eine echte Debatte wächst nach vorn, und niemand darin weiß, wer als Nächstes antwortet.

<!-- !!== label=b-answers party=b answers="Dauerhafte Antworten im Kontext" ==== -->

Diese Antwort hängt am ersten Eintrag jener Liste und ist zugleich ein eigenständiger Beitrag. Weil sie sich auf Segment `{{anchor}}` bezieht, lautet ihr Schlüssel `{{key}}`, und ihre eigenen Segmente heißen `{{key}}1`, `{{key}}2` und so fort.

Was diese Anordnung ermöglicht:

- Eine Antwort erscheint unmittelbar unter dem Segment, auf das sie sich bezieht. **Ein Segment ist damit doppelt an seinen Zusammenhang gebunden — durch seinen Schlüssel und durch den Ort, an dem es steht.** Ganze Antwortebenen lassen sich zuklappen, wenn eine Seite unübersichtlich wird.
- Eine Antwort hebt sich durch Farbe und Einrückung vom umgebenden Beitrag ab, sodass immer erkennbar bleibt, wessen Text man gerade liest.
- Beliebig viele Parteien können teilnehmen, jede mit ihrem eigenen Buchstaben. Dieser Buchstabe wird übrigens Teil des Schlüssels jedes Beitrags dieser Partei (siehe das Beispiel weiter unten).
- Beiträge können in Markdown geschrieben werden.

Weil der Zusammenhang einer Antwort technisch an das Segment gebunden ist, funktioniert es nicht, eine Partei aus dem Zusammenhang gerissen zu zitieren. Der umgebende Text, und damit der ursprüngliche Zusammenhang, ist höchstens einen Klick entfernt.

<!-- !!== label=a-example party=a answers="Beliebig viele Parteien können teilnehmen" ==== -->

### Ein Beispiel

Stell dir eine Debatte mit drei Parteien vor.

- Partei `a` eröffnet sie mit dem ersten Beitrag `a`. Seine Segmente heißen `a1`, `a2` und so weiter.
- Partei `b` widerspricht an zwei Stellen. Sie beantwortet Segment 7 mit einem Beitrag namens `a7b` und Segment 10 mit einem weiteren namens `a10b`. Die Segmente innerhalb dieser Beiträge heißen `a7b1`, `a7b2` sowie `a10b1`, `a10b2`. Beachte, dass ein Beitragsschlüssel auf einen Buchstaben endet, ein Segmentschlüssel auf eine Zahl.
- Partei `c` kommt hinzu, liest den Wortwechsel und antwortet auf Segment 4 von `a7b`. Ihr Beitrag heißt `a7b4c`.
- Partei `a` meldet sich zurück, um ein Missverständnis im zweiten Segment jener Antwort auszuräumen, woraus `a7b4c2a` wird.

Ein Schlüssel ist ein Pfad. Von links nach rechts gelesen benennt er jeden Schritt vom Eröffnungsbeitrag hinunter bis zu der Antwort, die vor dir steht. Deshalb lässt sich keine Antwort von dem ablösen, worauf sie sich bezieht.

### Warum sich der Aufwand lohnt

Eine Auseinandersetzung wird dadurch feinkörnig. Ein einzelner Punkt lässt sich genau ansprechen, und eine Meinungsverschiedenheit lässt sich bis dorthin verfolgen, wo sie tatsächlich beginnt — oft bei einer Annahme, die keine der beiden Seiten ausgesprochen hatte. Zugleich geht der größere Zusammenhang nie verloren, weil jeder Beitrag dort verankert bleibt, wo er hingehört. Und da jedes Segment einen Schlüssel hat, kostet es nichts, sich genau auf etwas zu beziehen.

<!-- !!== label=a-markdown party=a answers="Beiträge können in Markdown geschrieben werden" ==== -->

Markdown fügt Formatierungen über eine Handvoll gewöhnlicher Zeichen hinzu — `**fett**` ergibt zum Beispiel **fett**. Eine kurze Einführung findest du unter <https://de.wikipedia.org/wiki/Markdown>.

<!-- !!== label=b-integrity party=b answers="Beweisbare Integrität der Inhalte" ==== -->

### Warum das wichtig ist

Wie jede Infrastruktur wird auch eine Debattenplattform von Menschen betrieben. In einer wirklich strittigen Auseinandersetzung besteht die Gefahr, dass der Betreiber in die Inhalte eingreift, indem er löscht oder verändert. Eine zweite Gefahr weist in die Gegenrichtung — dass einem Betreiber genau das vorgeworfen wird, obwohl er es nicht getan hat, etwa nachdem eine Auseinandersetzung für die vorwerfende Seite schlecht ausgegangen ist.

Indem diese Plattform technische Mittel für unabhängige Manipulationsprüfungen bereitstellt, kann sie zu einem neutralen Boden für strittige Debatten werden.

### Wie das gemacht wird

*Fair Debate* begegnet beiden Gefahren, indem es die Inhalte aus der eigenen Datenbank heraushält. Jeder Beitrag ist eine einfache Textdatei, festgehalten in einem versionierten, öffentlich lesbaren Repository — eines je Debatte. Die Plattform stellt eine Debatte dar, indem sie diese Dateien liest. Veröffentlicht jemand einen Beitrag, entsteht dabei ein neuer Commit mit Zeitstempel, Fingerabdruck und kryptografischer Signatur. Und weil jeder Fingerabdruck auch auf Basis des vorherigen berechnet wird, bilden die Commits eine Kette. Wird ein alter Beitrag nachträglich verändert, ändern sich dadurch alle Fingerabdrücke ab dieser Stelle.

Das mag nach nebensächlicher Technik klingen, aber signierte Commits in öffentlich lesbaren Repositories versetzen *jeden* in die Lage, eine Manipulation zu erkennen (an den veränderten Fingerabdrücken) und sie zu beweisen (mit den kryptografischen Commit-Signaturen). Das ist ein grundlegender Unterschied zum klassischen Veröffentlichen im Netz, wo derjenige, der den Server kontrolliert, auch kontrolliert, was dieser anzeigt, und es folglich ändern kann. Nutzerinnen und Nutzer könnten zwar Bildschirmfotos aufheben, aber sie könnten nie beweisen, dass diese nicht gefälscht sind.

### Warum die Signatur nötig ist

Ohne sie ist ein Fingerabdruck, den du dir gespeichert hast, nur deine eigene Behauptung, und der Betreiber kann entgegnen, du habest diese Datei selbst geschrieben. Die Signatur macht daraus eine Aussage der Plattform. Indem sie einen Commit signiert, bezeugt die Plattform, dass dies die Fassung ist, die sie veröffentlicht hat. Tauchen also zwei unterschiedlich signierte Fassungen derselben Vorgeschichte auf, steht sie für beide ein, und eine davon muss falsch sein. Als Ausrede bleibt dann nur noch, der Schlüssel sei gestohlen worden — ebenfalls keine bequeme Lage.

Die Signatur reist mit dem Repository mit, wer es also klont, hat dieses Beweismittel in der Hand. In einer strittigen Debatte hat die Gegenseite das allergrößte Interesse daran, eine solche Kopie zu behalten, und interessierte Beobachter wie Journalistinnen und Journalisten ebenso.

### Wo du nachschauen kannst

Jeder Beitrag trägt einen Link zur Integritätsseite seiner Debatte, erreichbar über das Lupensymbol. Dort sind die Fingerabdrücke aufgelistet, und das Repository mit den signierten Commits lässt sich als einzelne Datei herunterladen oder direkt mit git klonen. Außerdem beschreibt diese Seite, wie sich Manipulationen an den Inhalten aufspüren lassen.

Wer an einer Debatte teilnimmt, geht am kürzesten Weg, indem er dieses Repository einmal klont. Von da an übernimmt ein einzelnes `git pull --ff-only` die Prüfung. Es läuft still durch, solange die Debatte nur wächst, und es verweigert den Dienst in dem Moment, in dem die Vorgeschichte umgeschrieben wurde. Du musst dir nichts notieren und nichts merken, und die Verweigerung lässt dich beide Fassungen zugleich in der Hand halten — das ist es, was aus einem Verdacht etwas Vorzeigbares macht.

### Was zugesagt wird und was nicht

Die Plattform kann nicht zusagen, dass die Commit-Vorgeschichte niemals verändert wird. Es kann Fälle geben, in denen Inhalte daraus entfernt werden müssen, etwa personenbezogene Angaben. Zugesagt wird stattdessen, dass jede Änderung an der Vorgeschichte sichtbar ist. Sie zerreißt die Kette der Fingerabdrücke, und sie wird auf der Integritätsseite der betroffenen Debatte vermerkt. Eine zerrissene Kette ohne einen solchen Vermerk bedeutet Manipulation.

Das genaue Verfahren für ein solches Entfernen ist allerdings noch nicht festgelegt.

### Aktueller Stand

Ein wirklich wasserdichtes System für Integritätsprüfungen aufzubauen, das für die meisten Menschen trotzdem verständlich bleibt, ist tatsächlich nicht einfach. Der jetzige Ansatz ist daher ein Kompromiss und noch in Arbeit. Er bietet aber schon jetzt deutlich mehr Sicherheit als das, was sonst üblich ist.

Diese Debatte ist, wie einige andere auch, ein Anschauungsstück. Ihr Repository wird jedes Mal neu gebaut, wenn sich die Erklärung ändert. Ihre Verfasser, ihre Commits, deren Zeitpunkte und Fingerabdrücke sind deshalb erfunden, obwohl die Integritätsseite sie so zeigt, wie sie es bei einer echten Debatte täte. Für die Debatten, die hier tatsächlich geführt werden, gilt alles oben Beschriebene unverändert.

<!-- !!== label=c-critical party=c answers="ist daher ein Kompromiss" ==== -->

Was sind die Schwachstellen dieses Ansatzes?

<!-- !!== label=a-evolution party=a answers="Was sind die Schwachstellen dieses Ansatzes?" ==== -->

Zurzeit gibt es die folgenden Schwachstellen.

### Bedienbarkeit

- Fingerabdrücke und Signaturen der Commits zu prüfen erfordert derzeit einige technische Kenntnisse, etwa das Ausführen von Befehlen auf der Kommandozeile. Eigens dafür gebaute Software könnte das vereinfachen, aber diese Software müsste von einer unabhängigen Stelle betreut oder wenigstens geprüft werden. Ein Prüfwerkzeug, das von derselben Stelle kontrolliert wird, die es prüfen soll, ist sinnlos.

### Tatsächliche Integrität

- Das Szenario für einen böswilligen Betreiber ist hier eher ein Abstreiten als ein Angriff. Mit zwei signierten Fassungen derselben Vorgeschichte konfrontiert, könnte die Plattform behaupten, ihr Signaturschlüssel sei gestohlen worden und eine dieser Signaturen sei daher nicht von ihr. Das Repository allein widerlegt das nicht. Helfen würde eine Kopie des Repositories bei einer unabhängigen und vertrauenswürdigen dritten Stelle, und die gibt es noch nicht. Die Gefahr selbst ist gering, denn dass ein Signaturschlüssel die Plattform verlässt, ist unwahrscheinlich. Schlüsselwechsel können trotzdem aus gewöhnlichen Gründen nötig werden, und die sind harmlos. Solange ein Schlüsselwechsel nicht mit einem Widerspruch in der Commit-Vorgeschichte zusammenfällt, gibt es nichts zu erklären.
- Es wird Fälle geben, in denen das Verändern der Commit-Vorgeschichte nötig ist. Dieses erklärende Repository muss zum Beispiel gemeinsam mit der Software aktualisiert werden, oder rechtswidrige Beiträge müssen von der Plattform entfernt werden. Ein sauberer Weg, solche Fälle zu behandeln und zu dokumentieren, ist derzeit noch nicht umgesetzt.
- Das Integritätskonzept und seine Umsetzung sind noch nicht von unabhängigen Fachleuten geprüft worden. Es ist daher nicht unwahrscheinlich, dass Fair Debate Sicherheitslücken hat. Das ist allerdings ein allgemeines Problem von Software, und sich dessen bewusst zu sein ist meist ein wichtiger Schritt, um schwerwiegende Vorfälle zu verhindern.
- Ein Fingerabdruck zeigt, dass ein Text seit seiner Veröffentlichung unverändert ist. Er zeigt nicht, wer ihn geschrieben hat. Die Commits werden von dieser Plattform erzeugt und signiert, nicht von den Verfassenden, die Plattform könnte also im Prinzip einen Beitrag unter fremdem Namen einstellen. Signaturen der Beitragenden selbst würden diese Lücke schließen und gibt es hier noch nicht.
- Die Plattform könnte einer Leserin eine Vorgeschichte zeigen und einem anderen Leser eine abweichende, und beide signieren. Das fällt erst auf, wenn die beiden sich austauschen — genau das würde ein öffentlicher Spiegel der Repositories selbsttätig erledigen. Einen solchen gibt es noch nicht.
- Wer den Server kontrolliert, kontrolliert auch den Signaturschlüssel, und dazu zählen die Verwaltenden des Rechenzentrums. Diese Gefahr bringt jede IT-Infrastruktur mit sich. Was böswillige Akteure allerdings nicht können, ist bereits herausgegebene Signaturen zurückzunehmen. Eine Manipulation bleibt daher erkennbar und lässt sich aufklären.


<!-- !!== label=a-selfreply party=a answers="Eine Partei kann auch ein eigenes Segment beantworten" ==== -->

Das hier ist so ein Fall. Der Beitrag stammt von Partei `a` und beantwortet ein Segment von Partei `a`, und die Plattform kennzeichnet ihn als Selbstantwort, damit ihn niemand für den einer anderen Partei hält. Der nützliche Fall ist nicht diese Vorführung, sondern die Richtigstellung. Ein Nachtrag oder das Eingeständnis eines Fehlers landet unmittelbar neben dem Satz, um den es geht, statt weit darunter, wo ihn niemand sieht, der das Ursprüngliche liest.

<!-- !!== label=b-faq-alphabet party=b answers="mehr Parteien an der Debatte teilnehmen, als das Alphabet Buchstaben hat" ==== -->

Die Buchstaben laufen einfach weiter. Nach `z` gehen die Bezeichner zweistellig weiter, mit `aa`, `ab` und so fort, in der Reihenfolge des Beitritts. Es gibt also keine Obergrenze im Schlüsselsystem, und ein Schlüssel wie `a5aa` ist ein ganz gewöhnlicher Schlüssel — Partei `aa` antwortet auf Segment 5 des Eröffnungsbeitrags. In der Praxis wird eine Debatte mit 26 aktiven Parteien allerdings andere Probleme zuerst haben.

<!-- !!== label=b-faq-references party=b answers="Können mehrere Segmente oder Teile von Segmenten beantwortet werden?" ==== -->

Beides ist möglich, und der Schlüssel sagt, was gemeint ist. Eine Folge zusammenhängender Segmente wird `a5-7b` geschrieben, zu lesen als Partei `b` beantwortet die Segmente 5 bis 7 des Beitrags `a`. Einzelne Wörter innerhalb eines Segments werden `a7_4-8b` geschrieben, also die Wörter 4 bis 8 des Segments `a7`. Gezählt wird dabei auf der Textdatei im Repository, nicht auf der dargestellten Seite, und die Zählregel ist bewusst einfach und unveränderlich. So kann jeder durch Lesen der Datei nachprüfen, worauf eine Wortangabe zeigt, ohne der Plattform glauben zu müssen.

<!-- !!== label=a-faq-integrity party=a answers="Wie lässt sich die Integrität einer Debatte prüfen" ==== -->

Jeder Beitrag trägt ein kleines Lupensymbol, das zur Integritätsseite seiner Debatte führt. Diese Seite listet den Fingerabdruck jedes Commits auf, nennt den Signaturschlüssel der Plattform, gibt das ganze Repository als git-Klon heraus und erklärt im Einzelnen, wie sich Fingerabdrücke und Signaturen prüfen lassen. Das Repository trägt dieselbe Anleitung in seiner eigenen README, eine Kopie davon erklärt sich also selbst.

Die kurze Antwort lautet, dass du das Repository einmal klonst und bei jeder Rückkehr `git pull --ff-only` ausführst. Neue Beiträge kommen kommentarlos an; bei einer umgeschriebenen Vorgeschichte verweigert der Befehl den Dienst und sagt das auch. Umschreiben ist nicht automatisch ein Angriff, denn Beiträge müssen gelegentlich aus organisatorischen oder rechtlichen Gründen entfernt werden. Unsichtbar ist es aber nie, und ein solcher Vorgang soll auf der Integritätsseite angekündigt und begründet werden.

<!-- !!== label=a-faq-moderation party=a answers="Wie wird die Plattform moderiert?" ==== -->

Eine Debatte hat drei Stufen der Auffindbarkeit. *Öffentlich* bedeutet gelistet und für alle lesbar, *versteckt* bedeutet nur über den Link lesbar und nirgends gelistet, *privat* bedeutet nur für die Teilnehmenden und die Moderation lesbar. Die Auffindbarkeit einer Debatte zu ändern kann die Zustimmung sowohl der Moderation als auch der Teilnehmenden erfordern. Öffentliche Beiträge neuer Konten starten zum Beispiel versteckt und müssen von der Moderation freigegeben werden. Und eine öffentliche Debatte kann nur dann auf privat gestellt werden, wenn alle Parteien zustimmen oder die Moderation es durchsetzt. Andernfalls könnte eine Partei, die eine Auseinandersetzung verloren hat, eine Debatte einfach aus der Öffentlichkeit tilgen. Teile davon werden noch gebaut. Heute wird eine Moderationsentscheidung über die Verwaltungsoberfläche getroffen.

<!-- !!== label=a-faq-feedback party=a answers="Wie sammelt das Projekt Rückmeldungen?" ==== -->

Über die [Kontaktseite](/contact/) dieser Website, die auf die Betreuung des Projekts und auf das öffentliche Quelltext-Repository verweist, wo sich Fehlermeldungen und Vorschläge einreichen lassen. Ein Rückmeldeformular innerhalb der Plattform selbst gibt es noch nicht.

<!-- !!== label=a-faq-help party=a answers="Kann man das Projekt unterstützen?" ==== -->

Ja. Verbesserungsvorschläge und Ideen sind immer willkommen. Benutze die Plattform für echte Auseinandersetzungen und melde, wo sie dir im Weg stand. Beachte allerdings, dass die Plattform sich vorbehält zu moderieren, was öffentlich sichtbar wird — siehe die Frage zur Moderation. Darüber hinaus ist der Quelltext öffentlich, und die Möglichkeiten reichen vom Beheben eines Tippfehlers in genau diesen Texten bis zum Prüfen des Integritätskonzepts.
