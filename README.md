# lampa-iptv (tv.team fork)

Форк плагина IPTV для Lampa (`https://cub.red/plugin/iptv`) под плейлист tv.team.

Изменения (см. `diff iptv.orig.js iptv.js`):
- XMLTV без атрибутов: `<title>`, `<desc>`, `<category>`, `<display-name>` без `lang` — у epg.team именно так, оригинал их не видел.
- Телегид держится в памяти (окно −12 ч…+48 ч, только каналы плейлиста) — запись в IndexedDB у оригинала теряла часть каналов.
- Телегид загружается при каждом запуске; источник по умолчанию `https://epg.team/3.1.xml.gz`.
- Сохраняется последний канал файла (оригинал его терял).

Установка в Lampa: Настройки → Расширения → Добавить плагин → `https://patr56.github.io/lampa-iptv/iptv.js` (оригинальный IPTV удалить).
