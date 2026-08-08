# Руководство по миграции на рефакторенную версию

## Быстрый старт

Рефакторенная версия готова к запуску немедленно.

### Запуск рефакторенного приложения

```bash
# Вариант 1: Через скрипт
./run_refactored.sh

# Вариант 2: Напрямую
python3 backend/app_refactored.py

# Вариант 3: С пользовательским портом
PORT=8081 python3 backend/app_refactored.py

# Вариант 4: С пользовательской БД
TRAVELER_DB=/var/lib/traveler/traveler.sqlite3 python3 backend/app_refactored.py
```

## Полная миграция

### Этап 1: Резервная копия (опционально)

```bash
# Сохраните текущую версию на случай нужности откатиться
cp backend/app.py backend/app_original.py
cp static/app.js static/app_original.js
```

### Этап 2: Замена бэкенда

```bash
# Переименуйте старый файл
mv backend/app.py backend/app_legacy.py

# Скопируйте рефакторенную версию как основную
cp backend/app_refactored.py backend/app.py
```

### Этап 3: Замена фронтенда (если нужен старый код)

Фронтенд автоматически использует новые модули (в папке `static/js/`). Если нужно вернуться:

```bash
# Переименуйте новый модульный js
mv static/app.js static/app_modular.js

# Восстановите старый (если сохранили резервную копию)
cp static/app_original.js static/app.js

# Обновите index.html для использования старого скрипта
# Измените: <script type="module" src="js/app.js"></script>
# На: <script src="app.js"></script>
```

### Этап 4: Тестирование

Откройте браузер и проверьте:
- ✅ Список путешествий загружается
- ✅ Можно создать новое путешествие
- ✅ Расходы добавляются
- ✅ Займы работают
- ✅ Журнал обновляется

## Откат на старую версию

Если возникли проблемы:

### Откат бэкенда
```bash
# Стоп текущего процесса
# Ctrl+C

# Восстановите оригинальный файл
mv backend/app.py backend/app_refactored.py
mv backend/app_legacy.py backend/app.py

# Перезапустите
python3 backend/app.py
```

### Откат фронтенда
```bash
# В index.html измените строку скрипта с:
<script type="module" src="js/app.js"></script>

# На:
<script src="app_original.js"></script>
```

## Проверка совместимости

Обе версии используют **одну и ту же БД** - это не проблема. Можете запускать их поочередно без потери данных.

```bash
# Запустите рефакторенную версию
python3 backend/app_refactored.py &

# Нажмите Ctrl+C

# Запустите оригинальную версию - данные все там
python3 backend/app.py
```

## Для разработчиков

### Добавление нового функционала в рефакторенную версию

#### В бэкенде:

1. **Создайте новый модель** в `backend/models/`:
```python
# backend/models/photo.py
class Photo:
    @staticmethod
    def upload(trip_id, family_id, file_path): ...
```

2. **Зарегистрируйте в `__init__.py`**:
```python
# backend/models/__init__.py
from .photo import Photo
__all__ = [..., "Photo"]
```

3. **Добавьте роут в `app_refactored.py`**:
```python
if tail == "photos" and self.command == "POST":
    photo_id = Photo.upload(trip_id, family_id, ...)
    return self.send_json({"id": photo_id}, HTTPStatus.CREATED)
```

#### На фронтенде:

1. **Добавьте API функцию** в `static/js/api.js`:
```javascript
export function uploadPhoto(tripId, familyId, file) {
    const fd = new FormData();
    fd.append("file", file);
    return api(`/api/trips/${tripId}/families/${familyId}/photos`, {
        method: "POST",
        body: fd,
    });
}
```

2. **Добавьте renderer** в `static/js/renderer.js`:
```javascript
export function renderPhotos(photos) {
    qs("#photosList").innerHTML = photos
        .map(p => `<img src="${p.url}" />`)
        .join("");
}
```

3. **Добавьте обработчик формы** в `static/js/forms.js`:
```javascript
qs("#photoForm").addEventListener("submit", async (e) => {
    const file = e.target.elements.file.files[0];
    await uploadPhoto(state.tripId, familyId, file);
    await onDataChange();
});
```

## Производительность

Рефакторенная версия имеет **идентичную производительность** оригинальной:
- Те же API endpoints
- Та же логика вычислений
- Те же запросы в БД

Преимущества рефакторинга чисто в **поддерживаемости кода**, а не в производительности.

## Часто задаваемые вопросы

### Вопрос: Могу ли я запускать обе версии одновременно?

**Ответ:** Да, они работают с одной БД, но не одновременно на одном порту:
```bash
# Терминал 1
PORT=8080 python3 backend/app.py

# Терминал 2
PORT=8081 python3 backend/app_refactored.py
```

### Вопрос: Совместимы ли данные между версиями?

**Ответ:** Полностью совместимы. БД одна и та же, обе версии работают с ней одинаково.

### Вопрос: Нужно ли менять фронтенд?

**Ответ:** Нет, фронтенд полностью независим от версии бэкенда. Обновили фронтенд для улучшения кода, но он работает с обоими.

### Вопрос: Какие браузеры поддерживает новый фронтенд?

**Ответ:** Модули ES6 поддерживаются:
- Chrome 61+
- Firefox 67+
- Safari 11.1+
- Edge 79+

Для старых браузеров используйте `app_original.js` или добавьте бандлер.

## Поддержка

Если возникли проблемы:

1. Проверьте логи приложения (в консоли где запущено)
2. Откройте DevTools в браузере (F12) и проверьте ошибки
3. Попробуйте очистить localStorage и перезагрузиться:
   ```javascript
   // В консоли браузера
   localStorage.clear();
   location.reload();
   ```
4. Откатитесь на оригинальную версию если нужно
