<template>
  <div class="admin-page">
    <header>
      <router-link to="/" class="back-link">← К доске</router-link>
      <h1>Администрирование</h1>
    </header>

    <nav class="admin-nav">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        type="button"
        class="nav-tab"
        :class="{ active: activeSection === tab.id }"
        @click="activeSection = tab.id"
      >
        {{ tab.label }}
      </button>
    </nav>

    <section v-if="activeSection === 'users'" class="card">
      <h2>Пользователи</h2>
      <table class="users-table">
        <thead>
          <tr>
            <th></th>
            <th>Имя</th>
            <th>Логин</th>
            <th>Email</th>
            <th>Команды</th>
            <th>Роль</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.id">
            <td><Avatar :user="u" :size="26" /></td>
            <td>{{ u.full_name }} <span v-if="u.is_admin" class="admin-tag">админ</span></td>
            <td class="muted">{{ u.username }}</td>
            <td class="muted">{{ u.email || "—" }}</td>
            <td>
              <span v-if="!u.teams?.length" class="muted">—</span>
              <span v-for="t in u.teams" :key="t.id" class="chip">{{ t.name }}</span>
            </td>
            <td>{{ roleLabel(u.role) }}</td>
            <td class="rule-actions">
              <button type="button" class="link-btn" @click="openEditUser(u)">Изменить</button>
              <button
                v-if="!u.is_admin"
                type="button"
                class="link-btn danger"
                @click="removeUser(u)"
              >
                Удалить
              </button>
            </td>
          </tr>
        </tbody>
      </table>

      <div class="inline-form" style="margin: 12px 0 4px">
        <button type="button" class="btn" @click="openCreateUser">Создать пользователя</button>
      </div>
      <p v-if="userActionError" class="error-text">{{ userActionError }}</p>

      <div v-if="showUserModal" class="overlay" @click.self="closeUserModal">
        <div class="rule-modal">
          <h3>{{ editingUserId ? "Редактирование пользователя" : "Новый пользователь" }}</h3>
          <form class="stack-form" @submit.prevent="submitUserForm">
            <label>
              Логин
              <input v-model="userForm.username" type="text" required autocomplete="off" />
            </label>
            <label>
              Пароль
              <input
                v-model="userForm.password"
                type="password"
                :required="!editingUserId"
                autocomplete="new-password"
                :placeholder="editingUserId ? 'Оставьте пустым, чтобы не менять' : ''"
              />
            </label>
            <label>
              Имя
              <input v-model="userForm.full_name" type="text" required />
            </label>
            <label>
              Email
              <input v-model="userForm.email" type="email" />
            </label>
            <label>
              О себе
              <textarea v-model="userForm.bio" rows="3"></textarea>
            </label>
            <label>
              Роль
              <select v-model="userForm.role">
                <option value="creator">Может ставить задачи</option>
                <option value="executor">Исполнитель</option>
                <option value="observer">Наблюдатель</option>
              </select>
            </label>
            <label class="checkbox-row">
              <input v-model="userForm.is_admin" type="checkbox" />
              Администратор
            </label>
            <div class="inline-form">
              <button class="btn" type="submit" :disabled="userFormLoading">
                {{ editingUserId ? "Сохранить" : "Создать" }}
              </button>
              <button type="button" class="btn secondary" @click="closeUserModal">Отмена</button>
            </div>
            <p v-if="userFormError" class="error-text">{{ userFormError }}</p>
          </form>
        </div>
      </div>
    </section>

    <section v-if="activeSection === 'teams'" class="card">
      <h2>Команды</h2>
      <div class="teams-list">
        <div v-for="t in teams" :key="t.id" class="team-block">
          <div class="team-header">
            <strong>{{ t.name }}</strong>
            <button class="link-btn danger" @click="removeTeam(t)">Удалить команду</button>
          </div>
          <div class="member-chips">
            <span v-for="m in t.members" :key="m.id" class="chip removable">
              {{ m.full_name }}
              <button type="button" class="chip-remove" @click="removeMember(t, m)">×</button>
            </span>
            <span v-if="t.members.length === 0" class="muted">Нет участников</span>
          </div>
          <div class="add-member">
            <select :value="''" @change="onAddMember(t, $event)">
              <option value="" disabled selected>Добавить участника...</option>
              <option v-for="u in nonMembers(t)" :key="u.id" :value="u.id">{{ u.full_name }}</option>
            </select>
            <span v-if="nonMembers(t).length === 0" class="muted">Все пользователи уже в команде</span>
          </div>
        </div>
      </div>

      <form class="inline-form" @submit.prevent="submitNewTeam">
        <input v-model="newTeamName" type="text" placeholder="Название команды" required />
        <button class="btn" type="submit" :disabled="newTeamLoading">Создать команду</button>
      </form>
      <p v-if="teamError" class="error-text">{{ teamError }}</p>
    </section>

    <section v-if="activeSection === 'permissions'" class="card">
      <h2>Действия с задачами</h2>
      <p class="hint">
        Какие действия доступны роли. «Свои» — задачи, где пользователь постановщик.
        «Любые» — все видимые задачи. Администратор всегда может всё.
      </p>
      <table class="users-table role-perm-table">
        <thead>
          <tr>
            <th>Роль</th>
            <th>Создавать</th>
            <th>Редактировать свои</th>
            <th>Удалять свои</th>
            <th>Редактировать любые</th>
            <th>Удалять любые</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="rp in rolePermissions" :key="rp.role">
            <td>{{ roleLabel(rp.role) }}</td>
            <td><input v-model="rp.can_create" type="checkbox" /></td>
            <td><input v-model="rp.can_edit" type="checkbox" /></td>
            <td><input v-model="rp.can_delete" type="checkbox" /></td>
            <td><input v-model="rp.can_edit_any" type="checkbox" /></td>
            <td><input v-model="rp.can_delete_any" type="checkbox" /></td>
            <td>
              <button
                type="button"
                class="link-btn"
                :disabled="rolePermLoading === rp.role"
                @click="saveRolePermission(rp)"
              >
                Сохранить
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="rolePermError" class="error-text">{{ rolePermError }}</p>
      <p v-if="rolePermOk" class="ok-text">{{ rolePermOk }}</p>

      <h2 class="form-section-title">Права между командами</h2>
      <p class="hint">
        Участники команды «От кого» смогут ставить задачи участникам команды «Кому».
        Внутри своей команды ставить задачи можно всегда без дополнительных прав.
      </p>

      <div class="permissions-list">
        <div v-for="p in permissions" :key="p.id" class="permission-row">
          <span class="chip">{{ p.from_team.name }}</span>
          <span class="arrow">→</span>
          <span class="chip">{{ p.to_team.name }}</span>
          <button class="link-btn danger" @click="removePermission(p)">Удалить</button>
        </div>
        <p v-if="permissions.length === 0" class="muted">Прав пока не настроено</p>
      </div>

      <form class="inline-form" @submit.prevent="submitNewPermission">
        <select v-model="newPermission.from_team_id" required>
          <option value="" disabled selected>От команды...</option>
          <option v-for="t in teams" :key="t.id" :value="t.id">{{ t.name }}</option>
        </select>
        <span class="arrow">→</span>
        <select v-model="newPermission.to_team_id" required>
          <option value="" disabled selected>Команде...</option>
          <option v-for="t in teams" :key="t.id" :value="t.id">{{ t.name }}</option>
        </select>
        <button class="btn" type="submit" :disabled="permissionLoading">Добавить право</button>
      </form>
      <p v-if="permissionError" class="error-text">{{ permissionError }}</p>

      <h2 class="form-section-title">Видимость воронок</h2>
      <p class="hint">
        Команда-владелец воронки (поле «команда» у воронки) видит её всегда.
        Общие воронки без команды видны всем.
        Ниже — доп. доступ: команда видит чужую воронку (и клиентов с задачами на ней).
      </p>
      <div class="permissions-list">
        <div v-for="p in funnelPermissions" :key="p.id" class="permission-row">
          <span class="chip">{{ p.team.name }}</span>
          <span class="arrow">видит</span>
          <span class="chip">{{ p.funnel.name }}</span>
          <button class="link-btn danger" @click="removeFunnelPermission(p)">Удалить</button>
        </div>
        <p v-if="funnelPermissions.length === 0" class="muted">Доп. доступов пока нет</p>
      </div>
      <form class="inline-form" @submit.prevent="submitFunnelPermission">
        <select v-model="newFunnelPermission.team_id" required>
          <option value="" disabled>Команда...</option>
          <option v-for="t in teams" :key="t.id" :value="t.id">{{ t.name }}</option>
        </select>
        <span class="arrow">видит</span>
        <select v-model="newFunnelPermission.funnel_id" required>
          <option value="" disabled>Воронку...</option>
          <option v-for="f in funnels" :key="f.id" :value="f.id">
            {{ f.name }}<template v-if="f.team"> ({{ f.team.name }})</template>
          </option>
        </select>
        <button class="btn" type="submit" :disabled="funnelPermLoading">Добавить</button>
      </form>
      <p v-if="funnelPermError" class="error-text">{{ funnelPermError }}</p>
    </section>

    <section v-if="activeSection === 'stages'" class="card">
      <h2>Воронки и стадии</h2>
      <p class="hint">
        У каждой команды (менеджеры, программисты и т.д.) может быть своя воронка со своими стадиями.
        Порядок воронок и стадий меняется перетаскиванием.
      </p>

      <div class="funnel-list">
        <div
          v-for="(f, idx) in funnels"
          :key="f.id"
          class="funnel-block"
          :class="{ active: selectedFunnelId === f.id }"
          draggable="true"
          @dragstart="onFunnelDragStart(idx)"
          @dragover.prevent
          @drop="onFunnelDrop(idx)"
          @click="selectedFunnelId = f.id"
        >
          <div class="funnel-block-head">
            <span class="drag-handle" title="Перетащить">⋮⋮</span>
            <strong>{{ f.name }}</strong>
            <span v-if="f.is_default" class="badge on">по умолчанию</span>
            <span v-if="f.team" class="muted"> · {{ f.team.name }}</span>
          </div>
          <div class="rule-actions" @click.stop>
            <button
              v-if="!f.is_default"
              type="button"
              class="link-btn"
              @click="makeFunnelDefault(f)"
            >
              По умолчанию
            </button>
            <button type="button" class="link-btn" @click="editFunnel(f)">Изменить</button>
            <button type="button" class="link-btn danger" @click="removeFunnel(f)">Удалить</button>
          </div>
        </div>
      </div>

      <h3>{{ editingFunnelId ? "Редактирование воронки" : "Новая воронка" }}</h3>
      <form class="stack-form" @submit.prevent="submitFunnelForm">
        <label>
          Название
          <input v-model="funnelForm.name" placeholder="Название воронки" required />
        </label>
        <label>
          Команда-владелец
          <select v-model="funnelForm.team_id">
            <option value="">Без команды (видна всем)</option>
            <option v-for="t in teams" :key="t.id" :value="t.id">{{ t.name }}</option>
          </select>
        </label>
        <label class="checkbox-row">
          <input v-model="funnelForm.is_default" type="checkbox" />
          Воронка по умолчанию
        </label>
        <p class="hint">
          По умолчанию открывается на доске и подставляется в автоматизации, если воронка не выбрана явно.
          Одновременно может быть только одна такая воронка.
        </p>
        <div class="inline-form">
          <button class="btn" type="submit" :disabled="funnelLoading">
            {{ editingFunnelId ? "Сохранить" : "Создать воронку" }}
          </button>
          <button
            v-if="editingFunnelId"
            type="button"
            class="btn secondary"
            @click="resetFunnelForm"
          >
            Отмена
          </button>
        </div>
      </form>
      <p v-if="funnelError" class="error-text">{{ funnelError }}</p>

      <template v-if="selectedFunnel">
        <h3>Стадии: {{ selectedFunnel.name }}</h3>
        <p class="hint">Перетащите строки, чтобы изменить последовательность колонок на доске.</p>
        <div
          v-for="(s, idx) in funnelStages"
          :key="s.id"
          class="stage-row"
          draggable="true"
          @dragstart="onStageDragStart(idx)"
          @dragover.prevent
          @drop="onStageDrop(idx)"
        >
          <span class="drag-handle" title="Перетащить">⋮⋮</span>
          <input v-model="s.name" @change="saveStageName(s)" />
          <label class="checkbox-row"><input type="checkbox" v-model="s.assignee_can_set" @change="saveStageFlags(s)" /> исполнитель</label>
          <label class="checkbox-row"><input type="checkbox" v-model="s.requires_result" @change="saveStageFlags(s)" /> результат</label>
          <label class="checkbox-row"><input type="checkbox" v-model="s.is_final" @change="saveStageFlags(s)" /> финал</label>
          <button type="button" class="link-btn danger" @click="removeStage(s)">Удалить</button>
        </div>
        <form class="inline-form" @submit.prevent="submitNewStage">
          <input v-model="newStageName" placeholder="Название стадии" required />
          <button class="btn" type="submit" :disabled="stageLoading">Добавить стадию</button>
        </form>
        <p v-if="stageError" class="error-text">{{ stageError }}</p>
      </template>
    </section>

    <section v-if="activeSection === 'automation'" class="card">
      <h2>Автоматизация</h2>
      <p class="hint">
        Правило = триггер + условия + действие.
        Пример: триггер «нет активности», условие «нет задачи на стадии», действие «создать задачу».
        Плейсхолдеры:
        <code>{date}</code>, <code>{rule}</code>, <code>{source_title}</code>,
        <code>{source_stage}</code>, <code>{client_name}</code>, <code>{client_company}</code>,
        <code>{client_email}</code>, <code>{notes}</code>, <code>{mail_subject}</code>,
        <code>{mail_from}</code>, <code>{mail_body}</code>.
      </p>

      <div v-for="rule in automationRules" :key="rule.id" class="rule-block">
        <div class="rule-header">
          <div>
            <strong>{{ rule.name }}</strong>
            <span class="badge" :class="rule.enabled ? 'on' : 'off'">
              {{ rule.enabled ? "вкл" : "выкл" }}
            </span>
          </div>
          <div class="rule-actions">
            <button type="button" class="link-btn" @click="editRule(rule)">Изменить</button>
            <button type="button" class="link-btn danger" @click="removeRule(rule)">Удалить</button>
          </div>
        </div>
        <div class="rule-meta">
          Триггер: {{ triggerLabel(rule) }}
          <span v-if="conditionsLabel(rule)"> · Условия: {{ conditionsLabel(rule) }}</span>
          · Действие: {{ actionLabel(rule) }}
          <template v-if="(rule.action_type || 'create_task') === 'send_email'">
            · «{{ rule.title_template }}» → {{ rule.email_to_template || "{client_email}" }}
          </template>
          <template v-else-if="rule.action_type === 'move_tasks'">
            · {{ moveScopeLabel(rule.move_scope) }}:
            {{ stageName(rule.move_from_stage_id) }} → {{ stageName(rule.target_stage_id) }}
          </template>
          <template v-else>
            · «{{ rule.title_template }}»
            <span v-if="rule.target_stage_id"> → {{ stageName(rule.target_stage_id) }}</span>
          </template>
          <span v-if="rule.last_run_at"> · последний запуск {{ formatDate(rule.last_run_at) }}</span>
        </div>
      </div>
      <p v-if="automationRules.length === 0" class="muted">Правил пока нет</p>
      <div class="inline-form" style="margin: 12px 0 4px">
        <button type="button" class="btn" @click="openCreateRuleModal">Создать правило</button>
      </div>

      <div
        v-if="showRuleModal"
        class="overlay"
        @click.self="closeRuleModal()"
      >
        <div class="rule-modal">
      <h3>{{ editingRuleId ? "Редактирование правила" : "Новое правило" }}</h3>
      <form class="stack-form" @submit.prevent="submitRule">
        <label>
          Название правила
          <input v-model="ruleForm.name" required />
        </label>
        <label class="checkbox-row">
          <input v-model="ruleForm.enabled" type="checkbox" />
          Включено
        </label>

        <h4 class="form-section-title">Триггер</h4>
        <label>
          Воронка триггера
          <select v-model="ruleForm.funnel_id">
            <option v-for="f in funnels" :key="f.id" :value="f.id">{{ f.name }}</option>
          </select>
        </label>
        <p class="hint">
          Стадии триггера и условий — из этой воронки.
          Стадию новой задачи / куда переместить можно выбрать в другой воронке ниже.
        </p>
        <label>
          Когда срабатывает
          <select v-model="ruleForm.trigger_type">
            <option value="schedule">По расписанию</option>
            <option value="status_change">При смене стадии</option>
            <option value="client_inactive">Нет активности по клиенту</option>
            <option value="client_email">Новое письмо от клиента</option>
          </select>
        </label>
        <p v-if="ruleForm.trigger_type === 'client_email'" class="hint">
          Срабатывает при каждом входящем письме, привязанном к клиенту (ответ на письмо
          из задачи или письмо с email клиента). Можно сузить условиями ниже.
          Для действия «отправить письмо» осторожнее с циклами автоответов.
        </p>

        <template v-if="ruleForm.trigger_type === 'schedule'">
          <label>
            Интервал
            <select v-model="ruleForm.schedule_interval">
              <option value="daily">Ежедневно</option>
              <option value="weekly">Еженедельно</option>
            </select>
          </label>
          <label>
            Время (МСК, ЧЧ:ММ)
            <input v-model="ruleForm.schedule_time" pattern="[0-9]{2}:[0-9]{2}" placeholder="09:00" required />
          </label>
          <label v-if="ruleForm.schedule_interval === 'weekly'">
            День недели
            <select v-model.number="ruleForm.schedule_weekday">
              <option :value="0">Понедельник</option>
              <option :value="1">Вторник</option>
              <option :value="2">Среда</option>
              <option :value="3">Четверг</option>
              <option :value="4">Пятница</option>
              <option :value="5">Суббота</option>
              <option :value="6">Воскресенье</option>
            </select>
          </label>
        </template>

        <template v-else-if="ruleForm.trigger_type === 'status_change'">
          <label>
            Из стадии (необязательно)
            <select v-model="ruleForm.watch_from_stage_id">
              <option value="">Любая</option>
              <option v-for="s in ruleStages" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
          </label>
          <label>
            В стадию
            <select v-model.number="ruleForm.watch_to_stage_id" required>
              <option v-for="s in ruleStages" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
          </label>
        </template>

        <template v-else-if="ruleForm.trigger_type === 'client_inactive'">
          <label>
            Дней без событий в таймлайне клиента
            <input
              v-model.number="ruleForm.inactivity_days"
              type="number"
              min="1"
              placeholder="например 30"
              required
            />
          </label>
        </template>

        <h4 class="form-section-title">Условия</h4>
        <label class="checkbox-row">
          <input v-model="ruleForm.condition_no_tasks" type="checkbox" />
          У клиента нет задач
        </label>
        <label class="checkbox-row">
          <input v-model="ruleForm.condition_no_stage_task" type="checkbox" />
          Нет задачи клиента на стадии
        </label>
        <template v-if="ruleForm.condition_no_stage_task">
          <label>
            Стадия без задач
            <select v-model.number="ruleForm.condition_stage_id" required>
              <option v-for="s in ruleStages" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
          </label>
        </template>
        <label>
          Клиент (пусто = все)
          <select v-model="ruleForm.condition_client_id">
            <option value="">Все клиенты</option>
            <option v-for="c in clientsList" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
        </label>

        <h4 class="form-section-title">Действие</h4>
        <label>
          Что выполнить
          <select v-model="ruleForm.action_type">
            <option value="create_task">Создать задачу</option>
            <option value="send_email">Отправить письмо</option>
            <option value="move_tasks">Переместить задачу(и) со стадии на стадию</option>
          </select>
        </label>

        <template v-if="ruleForm.action_type === 'create_task'">
          <label>
            Воронка новой задачи
            <select v-model="ruleForm.target_funnel_id">
              <option v-for="f in funnels" :key="f.id" :value="f.id">{{ f.name }}</option>
            </select>
          </label>
          <label>
            Стадия новой задачи
            <select v-model="ruleForm.target_stage_id">
              <option value="">Первая стадия воронки / по умолчанию</option>
              <option v-for="s in actionStages" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
          </label>
          <p class="hint">
            Например: триггер на воронке «Лиды», а задача создаётся на «Программисты → К выполнению».
          </p>
          <label>
            Шаблон названия задачи
            <input v-model="ruleForm.title_template" required />
          </label>
          <label>
            Шаблон описания
            <textarea v-model="ruleForm.description_template" rows="3"></textarea>
          </label>
          <label>
            Постановщик
            <select v-model.number="ruleForm.creator_id" required>
              <option v-for="u in users" :key="u.id" :value="u.id">{{ u.full_name }}</option>
            </select>
          </label>
          <label>
            Исполнители
            <select v-model="ruleForm.assignee_ids" multiple class="multi">
              <option v-for="u in users" :key="u.id" :value="u.id">{{ u.full_name }}</option>
            </select>
          </label>
          <label>
            Наблюдатели
            <select v-model="ruleForm.observer_ids" multiple class="multi">
              <option v-for="u in users" :key="u.id" :value="u.id">{{ u.full_name }}</option>
            </select>
          </label>
          <label>
            Срок через N дней (пусто = без срока)
            <input v-model="ruleForm.due_offset_days" type="number" min="0" placeholder="например 3" />
          </label>
        </template>

        <template v-else-if="ruleForm.action_type === 'send_email'">
          <label>
            Кому (email или шаблон)
            <input
              v-model="ruleForm.email_to_template"
              placeholder="{client_email} или user@example.com"
              required
            />
          </label>
          <label>
            Тема письма
            <input v-model="ruleForm.title_template" required />
          </label>
          <label>
            Текст письма
            <textarea v-model="ruleForm.description_template" rows="4"></textarea>
          </label>
          <label>
            От имени пользователя (для журнала)
            <select v-model.number="ruleForm.creator_id" required>
              <option v-for="u in users" :key="u.id" :value="u.id">{{ u.full_name }}</option>
            </select>
          </label>
          <p class="hint">
            Нужна настроенная SMTP-интеграция. Для клиента удобно указать
            <code>{client_email}</code>.
          </p>
        </template>

        <template v-else-if="ruleForm.action_type === 'move_tasks'">
          <label>
            Какие задачи перемещать
            <select v-model="ruleForm.move_scope">
              <option value="trigger_task">
                Задачу из события (письмо / смена стадии), если она на исходной стадии
              </option>
              <option value="client_stage">Все задачи клиента на исходной стадии</option>
              <option value="all_stage">Все задачи на исходной стадии</option>
            </select>
          </label>
          <label>
            Со стадии (воронка триггера)
            <select v-model.number="ruleForm.move_from_stage_id" required>
              <option v-for="s in ruleStages" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
          </label>
          <label>
            Воронка назначения
            <select v-model="ruleForm.target_funnel_id">
              <option v-for="f in funnels" :key="f.id" :value="f.id">{{ f.name }}</option>
            </select>
          </label>
          <label>
            На стадию
            <select v-model.number="ruleForm.target_stage_id" required>
              <option v-for="s in actionStages" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
          </label>
          <label>
            От имени пользователя (для журнала)
            <select v-model.number="ruleForm.creator_id" required>
              <option v-for="u in users" :key="u.id" :value="u.id">{{ u.full_name }}</option>
            </select>
          </label>
          <p class="hint">
            Для триггера «новое письмо от клиента» обычно выбирают
            «задачу из события» — переносится задача, на которую ответили письмом
            (если она на исходной стадии). Цепочка других правил по смене стадии
            не запускается.
          </p>
        </template>

        <div class="inline-form">
          <button class="btn" type="submit" :disabled="ruleLoading">
            {{ editingRuleId ? "Сохранить" : "Создать правило" }}
          </button>
          <button type="button" class="btn secondary" @click="closeRuleModal">
            Отмена
          </button>
        </div>
        <p v-if="ruleError" class="error-text">{{ ruleError }}</p>
      </form>
        </div>
      </div>
    </section>

    <section v-if="activeSection === 'templates'" class="card">
      <h2>Шаблоны писем</h2>
      <p class="hint">
        Шаблоны подставляются при отправке письма из задачи.
        Плейсхолдеры:
        <code>{date}</code>, <code>{source_title}</code>, <code>{source_id}</code>,
        <code>{source_stage}</code>, <code>{client_name}</code>, <code>{client_company}</code>,
        <code>{client_id}</code>, <code>{client_email}</code>, <code>{client_phone}</code>,
        <code>{notes}</code>.
      </p>

      <div v-for="t in messageTemplates" :key="t.id" class="rule-block">
        <div class="rule-header">
          <div>
            <strong>{{ t.name }}</strong>
            <div class="rule-meta">Тема: {{ t.subject_template || "—" }}</div>
          </div>
          <div class="rule-actions">
            <button type="button" class="link-btn" @click="editMessageTemplate(t)">Изменить</button>
            <button type="button" class="link-btn danger" @click="removeMessageTemplate(t)">Удалить</button>
          </div>
        </div>
      </div>
      <p v-if="messageTemplates.length === 0" class="muted">Шаблонов пока нет</p>

      <div class="inline-form" style="margin: 12px 0 4px">
        <button type="button" class="btn" @click="openCreateMessageTemplate">Создать шаблон</button>
      </div>
      <p v-if="templateError" class="error-text">{{ templateError }}</p>

      <div v-if="showTemplateModal" class="overlay" @click.self="closeTemplateModal">
        <div class="rule-modal">
          <h3>{{ editingTemplateId ? "Редактирование шаблона" : "Новый шаблон" }}</h3>
          <form class="stack-form" @submit.prevent="submitMessageTemplate">
            <label>
              Название
              <input v-model="templateForm.name" required />
            </label>
            <label>
              Тема письма
              <input v-model="templateForm.subject_template" placeholder="например Автоматизация ваших бизнес-процессов" />
            </label>
            <label>
              Текст письма
              <textarea v-model="templateForm.body_template" rows="8" placeholder="Можно оставить пустым"></textarea>
            </label>
            <div class="inline-form">
              <button class="btn" type="submit" :disabled="templateLoading">
                {{ editingTemplateId ? "Сохранить" : "Создать" }}
              </button>
              <button type="button" class="btn secondary" @click="closeTemplateModal">Отмена</button>
            </div>
            <p v-if="templateFormError" class="error-text">{{ templateFormError }}</p>
          </form>
        </div>
      </div>
    </section>

    <section v-if="activeSection === 'api'" class="card">
      <h2>API-токены</h2>
      <p class="hint">
        Токены для внешних систем. Базовый путь:
        <code>/api/v1</code>. Авторизация:
        <code>Authorization: Bearer &lt;token&gt;</code>
        или заголовок <code>X-API-Key</code>.
        Сырой токен показывается только при создании.
      </p>

      <div v-if="createdTokenValue" class="token-reveal">
        <strong>Скопируйте токен сейчас — повторно он не отобразится:</strong>
        <code class="token-value">{{ createdTokenValue }}</code>
        <button type="button" class="btn secondary" @click="copyCreatedToken">Копировать</button>
        <button type="button" class="link-btn" @click="createdTokenValue = ''">Скрыть</button>
      </div>

      <div v-for="t in apiTokens" :key="t.id" class="rule-block">
        <div class="rule-header">
          <div>
            <strong>{{ t.name }}</strong>
            <span class="badge" :class="t.enabled && !t.revoked_at ? 'on' : 'off'">
              {{ t.enabled && !t.revoked_at ? "активен" : "отозван" }}
            </span>
            <span class="muted"> · {{ t.token_prefix }}…</span>
          </div>
          <div class="rule-actions">
            <button
              v-if="t.enabled && !t.revoked_at"
              type="button"
              class="link-btn"
              @click="revokeToken(t)"
            >
              Отозвать
            </button>
            <button type="button" class="link-btn danger" @click="removeToken(t)">Удалить</button>
          </div>
        </div>
        <div class="rule-meta">
          Актор: {{ t.actor_user?.full_name || t.actor_user_id }}
          · создан {{ formatDate(t.created_at) }}
          <span v-if="t.last_used_at"> · использован {{ formatDate(t.last_used_at) }}</span>
        </div>
      </div>
      <p v-if="apiTokens.length === 0" class="muted">Токенов пока нет</p>

      <h3>Новый токен</h3>
      <form class="stack-form" @submit.prevent="submitApiToken">
        <label>
          Название
          <input v-model="tokenForm.name" placeholder="Интеграция CRM → 1С" required />
        </label>
        <label>
          Действия от имени
          <select v-model.number="tokenForm.actor_user_id" required>
            <option v-for="u in users" :key="u.id" :value="u.id">{{ u.full_name }}</option>
          </select>
        </label>
        <button class="btn" type="submit" :disabled="tokenLoading">Создать токен</button>
        <p v-if="tokenError" class="error-text">{{ tokenError }}</p>
      </form>

      <h3>Примеры запросов и ответов</h3>
      <p class="hint">
        Базовый URL: <code>{{ apiBaseUrl }}/api/v1</code>.
        Во всех запросах нужен токен:
        <code>Authorization: Bearer YOUR_TOKEN</code>
        или <code>X-API-Key: YOUR_TOKEN</code>.
      </p>

      <div class="api-auth-example">
        <div class="api-example-label">Заголовок авторизации</div>
        <pre class="api-code">Authorization: Bearer YOUR_TOKEN</pre>
      </div>

      <details
        v-for="ex in apiExamples"
        :key="ex.id"
        class="api-example"
        :open="ex.id === 'list-tasks'"
      >
        <summary>
          <span class="api-method" :class="ex.method.toLowerCase()">{{ ex.method }}</span>
          <code>{{ ex.path }}</code>
          <span class="muted">{{ ex.title }}</span>
        </summary>
        <p class="api-desc">{{ ex.description }}</p>

        <div class="api-example-label">curl</div>
        <pre class="api-code">{{ formatApiCurl(ex) }}</pre>

        <template v-if="ex.requestBody">
          <div class="api-example-label">Тело запроса (JSON)</div>
          <pre class="api-code">{{ ex.requestBody }}</pre>
        </template>

        <div class="api-example-label">Ответ {{ ex.responseStatus }}</div>
        <pre class="api-code">{{ ex.responseBody }}</pre>
      </details>
    </section>

    <section v-if="activeSection === 'email'" class="card">
      <h2>Интеграция с почтой</h2>
      <p class="hint">
        SMTP — отправка из задач. IMAP — получение ответов клиентов в историю переписки.
        Новые письма забираются фоном примерно каждые 30 секунд (и сразу при открытии
        вкладки «Почта» у задачи или клиента). Пароли хранятся на сервере; оставьте
        поле пустым, чтобы не менять текущий.
      </p>

      <form class="stack-form" @submit.prevent="submitEmailSettings">
        <h4 class="form-section-title">SMTP (исходящие)</h4>
        <label>
          SMTP хост
          <input v-model="emailForm.smtp_host" placeholder="smtp.example.com" required />
        </label>
        <label>
          Порт
          <input v-model.number="emailForm.smtp_port" type="number" required />
        </label>
        <label>
          Логин SMTP
          <input v-model="emailForm.smtp_user" />
        </label>
        <label>
          Пароль SMTP
          <input
            v-model="emailForm.smtp_password"
            type="password"
            :placeholder="emailSettings.has_password ? '•••••••• (сохранён)' : ''"
          />
        </label>
        <label>
          From (email)
          <input v-model="emailForm.from_email" type="email" required />
        </label>
        <label>
          From (имя)
          <input v-model="emailForm.from_name" />
        </label>
        <label class="checkbox-row">
          <input v-model="emailForm.use_tls" type="checkbox" />
          STARTTLS
        </label>
        <label class="checkbox-row">
          <input v-model="emailForm.use_ssl" type="checkbox" />
          SSL (обычно порт 465)
        </label>

        <h4 class="form-section-title">IMAP (входящие ответы)</h4>
        <label>
          IMAP хост
          <input v-model="emailForm.imap_host" placeholder="imap.example.com" />
        </label>
        <label>
          Порт IMAP
          <input v-model.number="emailForm.imap_port" type="number" />
        </label>
        <label>
          Логин IMAP (пусто = SMTP/From)
          <input v-model="emailForm.imap_user" />
        </label>
        <label>
          Пароль IMAP
          <input
            v-model="emailForm.imap_password"
            type="password"
            :placeholder="emailSettings.has_imap_password ? '•••••••• (сохранён)' : 'пусто = пароль SMTP'"
          />
        </label>
        <label>
          Папка
          <input v-model="emailForm.imap_folder" placeholder="INBOX" />
        </label>
        <label class="checkbox-row">
          <input v-model="emailForm.imap_use_ssl" type="checkbox" />
          IMAP SSL (обычно порт 993)
        </label>

        <div class="status-line">
          SMTP:
          <span :class="emailSettings.configured ? 'ok' : 'warn'">
            {{ emailSettings.configured ? "настроено" : "не настроено" }}
          </span>
          · IMAP:
          <span :class="emailSettings.imap_configured ? 'ok' : 'warn'">
            {{ emailSettings.imap_configured ? "настроено" : "не настроено" }}
          </span>
        </div>

        <div class="inline-form">
          <button class="btn" type="submit" :disabled="emailLoading">Сохранить</button>
          <input v-model="testTo" type="email" placeholder="email для теста" />
          <button
            type="button"
            class="btn secondary"
            :disabled="emailTestLoading || !testTo"
            @click="sendTestEmail"
          >
            {{ emailTestLoading ? "Отправка..." : "Тестовое письмо" }}
          </button>
        </div>
        <p v-if="emailError" class="error-text">{{ emailError }}</p>
        <p v-if="emailOk" class="ok-text">{{ emailOk }}</p>
      </form>
    </section>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted } from "vue";
import Avatar from "../components/Avatar.vue";
import {
  listAllUsers,
  createUser,
  updateUser,
  deleteUser,
  listTeams,
  createTeam,
  deleteTeam,
  addTeamMember,
  removeTeamMember,
  listPermissions,
  createPermission,
  deletePermission,
  listFunnelPermissions,
  createFunnelPermission,
  deleteFunnelPermission,
  listRolePermissions,
  updateRolePermission,
  getEmailSettings,
  saveEmailSettings,
  testEmail,
  listAutomationRules,
  createAutomationRule,
  updateAutomationRule,
  deleteAutomationRule,
  listApiTokens,
  createApiToken,
  revokeApiToken,
  deleteApiToken,
  listMessageTemplates,
  createMessageTemplate,
  updateMessageTemplate,
  deleteMessageTemplate,
} from "../api/admin";
import { listStages, createStage, updateStage, deleteStage, reorderStages } from "../api/stages";
import {
  listFunnels,
  createFunnel,
  updateFunnel,
  reorderFunnels,
  deleteFunnel,
} from "../api/funnels";
import { listClients } from "../api/clients";

const tabs = [
  { id: "users", label: "Пользователи" },
  { id: "teams", label: "Команды" },
  { id: "permissions", label: "Права" },
  { id: "stages", label: "Воронки" },
  { id: "automation", label: "Автоматизация" },
  { id: "templates", label: "Шаблоны писем" },
  { id: "api", label: "API" },
  { id: "email", label: "Почта" },
];
const activeSection = ref("users");

const users = ref([]);
const teams = ref([]);
const permissions = ref([]);
const funnelPermissions = ref([]);
const funnelPermLoading = ref(false);
const funnelPermError = ref("");
const newFunnelPermission = reactive({ team_id: "", funnel_id: "" });
const rolePermissions = ref([]);
const rolePermLoading = ref("");
const rolePermError = ref("");
const rolePermOk = ref("");
const stages = ref([]);
const funnels = ref([]);
const selectedFunnelId = ref(null);
const editingFunnelId = ref(null);
const funnelForm = reactive({
  name: "",
  team_id: "",
  is_default: false,
});
const funnelLoading = ref(false);
const funnelError = ref("");
const dragFunnelIndex = ref(null);
const dragStageIndex = ref(null);
const clientsList = ref([]);
const automationRules = ref([]);
const apiTokens = ref([]);
const createdTokenValue = ref("");
const tokenLoading = ref(false);
const tokenError = ref("");
const tokenForm = reactive({ name: "", actor_user_id: null });
const messageTemplates = ref([]);
const showTemplateModal = ref(false);
const editingTemplateId = ref(null);
const templateLoading = ref(false);
const templateError = ref("");
const templateFormError = ref("");
const templateForm = reactive({
  name: "",
  subject_template: "",
  body_template: "",
});
const emailSettings = ref({ configured: false, has_password: false });
const newStageName = ref("");
const stageError = ref("");
const stageLoading = ref(false);

const apiBaseUrl = computed(() => {
  if (typeof window !== "undefined" && window.location?.origin) {
    return window.location.origin;
  }
  return "http://localhost:8080";
});

const apiExamples = [
  {
    id: "list-tasks",
    title: "Поиск задач",
    method: "GET",
    path: "/api/v1/tasks?q=договор&client_id=1&stage_id=2&limit=20",
    description:
      "Фильтры: q (название/описание), client_id, stage_id, status (ключ стадии), limit (1–200).",
    requestBody: null,
    responseStatus: "200",
    responseBody: `[
  {
    "id": 3,
    "title": "Подготовить договор",
    "description": "Черновик для ООО Ромашка",
    "status": "backlog",
    "stage_id": 1,
    "due_date": "2026-11-15",
    "creator_id": 1,
    "client_id": 1,
    "assignee_ids": [2],
    "observer_ids": [],
    "created_at": "2026-11-07T14:26:00",
    "updated_at": "2026-11-07T14:26:00"
  }
]`,
  },
  {
    id: "get-task",
    title: "Получить задачу",
    method: "GET",
    path: "/api/v1/tasks/3",
    description: "Одна задача по id.",
    requestBody: null,
    responseStatus: "200",
    responseBody: `{
  "id": 3,
  "title": "Подготовить договор",
  "description": "Черновик для ООО Ромашка",
  "status": "backlog",
  "stage_id": 1,
  "due_date": "2026-11-15",
  "creator_id": 1,
  "client_id": 1,
  "assignee_ids": [2],
  "observer_ids": [],
  "created_at": "2026-11-07T14:26:00",
  "updated_at": "2026-11-07T14:26:00"
}`,
  },
  {
    id: "create-task",
    title: "Создать задачу",
    method: "POST",
    path: "/api/v1/tasks",
    description:
      "Если stage_id не указан — берётся первая стадия воронки по умолчанию. creator_id опционален (по умолчанию актор токена).",
    requestBody: `{
  "title": "Подготовить договор",
  "description": "Черновик для ООО Ромашка",
  "due_date": "2026-11-15",
  "client_id": 1,
  "stage_id": 1,
  "assignee_ids": [2],
  "observer_ids": [3]
}`,
    responseStatus: "201",
    responseBody: `{
  "id": 12,
  "title": "Подготовить договор",
  "description": "Черновик для ООО Ромашка",
  "status": "backlog",
  "stage_id": 1,
  "due_date": "2026-11-15",
  "creator_id": 1,
  "client_id": 1,
  "assignee_ids": [2],
  "observer_ids": [3],
  "created_at": "2026-11-07T17:30:00",
  "updated_at": "2026-11-07T17:30:00"
}`,
  },
  {
    id: "update-task",
    title: "Обновить задачу",
    method: "PUT",
    path: "/api/v1/tasks/12",
    description: "Передавайте только поля, которые нужно изменить.",
    requestBody: `{
  "stage_id": 2,
  "assignee_ids": [2, 4],
  "due_date": "2026-11-20"
}`,
    responseStatus: "200",
    responseBody: `{
  "id": 12,
  "title": "Подготовить договор",
  "description": "Черновик для ООО Ромашка",
  "status": "in_progress",
  "stage_id": 2,
  "due_date": "2026-11-20",
  "creator_id": 1,
  "client_id": 1,
  "assignee_ids": [2, 4],
  "observer_ids": [3],
  "created_at": "2026-11-07T17:30:00",
  "updated_at": "2026-11-07T17:35:00"
}`,
  },
  {
    id: "delete-task",
    title: "Удалить задачу",
    method: "DELETE",
    path: "/api/v1/tasks/12",
    description: "Удаляет задачу и связанные комментарии/события. Тело ответа пустое.",
    requestBody: null,
    responseStatus: "204",
    responseBody: "(пустое тело)",
  },
  {
    id: "list-clients",
    title: "Поиск клиентов",
    method: "GET",
    path: "/api/v1/clients?q=ромашка&limit=20",
    description: "Поиск по имени, компании, email, телефону.",
    requestBody: null,
    responseStatus: "200",
    responseBody: `[
  {
    "id": 1,
    "name": "ООО Ромашка",
    "company": "Ромашка",
    "email": "info@romashka.example",
    "phone": "+7 900 000-00-00",
    "notes": "VIP",
    "created_at": "2026-11-01T10:00:00",
    "updated_at": "2026-11-01T10:00:00",
    "tasks_count": 3
  }
]`,
  },
  {
    id: "get-client",
    title: "Получить клиента",
    method: "GET",
    path: "/api/v1/clients/1",
    description: "Один клиент по id.",
    requestBody: null,
    responseStatus: "200",
    responseBody: `{
  "id": 1,
  "name": "ООО Ромашка",
  "company": "Ромашка",
  "email": "info@romashka.example",
  "phone": "+7 900 000-00-00",
  "notes": "VIP",
  "created_at": "2026-11-01T10:00:00",
  "updated_at": "2026-11-01T10:00:00",
  "tasks_count": 3
}`,
  },
  {
    id: "create-client",
    title: "Создать клиента",
    method: "POST",
    path: "/api/v1/clients",
    description: "Обязательно только name.",
    requestBody: `{
  "name": "ООО Ромашка",
  "company": "Ромашка",
  "email": "info@romashka.example",
  "phone": "+7 900 000-00-00",
  "notes": "VIP"
}`,
    responseStatus: "201",
    responseBody: `{
  "id": 1,
  "name": "ООО Ромашка",
  "company": "Ромашка",
  "email": "info@romashka.example",
  "phone": "+7 900 000-00-00",
  "notes": "VIP",
  "created_at": "2026-11-07T17:30:00",
  "updated_at": "2026-11-07T17:30:00",
  "tasks_count": 0
}`,
  },
  {
    id: "update-client",
    title: "Обновить клиента",
    method: "PUT",
    path: "/api/v1/clients/1",
    description: "Частичное обновление — только переданные поля.",
    requestBody: `{
  "phone": "+7 900 111-22-33",
  "notes": "Перезвонили"
}`,
    responseStatus: "200",
    responseBody: `{
  "id": 1,
  "name": "ООО Ромашка",
  "company": "Ромашка",
  "email": "info@romashka.example",
  "phone": "+7 900 111-22-33",
  "notes": "Перезвонили",
  "created_at": "2026-11-07T17:30:00",
  "updated_at": "2026-11-07T17:40:00",
  "tasks_count": 0
}`,
  },
  {
    id: "delete-client",
    title: "Удалить клиента",
    method: "DELETE",
    path: "/api/v1/clients/1",
    description:
      "Клиент удаляется; задачи отвязываются (client_id → null). Тело ответа пустое.",
    requestBody: null,
    responseStatus: "204",
    responseBody: "(пустое тело)",
  },
];

function formatApiCurl(ex) {
  const url = `${apiBaseUrl.value}${ex.path}`;
  const lines = [`curl -X ${ex.method} '${url}' \\`, `  -H 'Authorization: Bearer YOUR_TOKEN'`];
  if (ex.requestBody) {
    lines[lines.length - 1] += " \\";
    lines.push(`  -H 'Content-Type: application/json' \\`);
    lines.push(`  -d '${ex.requestBody.replace(/\n/g, " ").replace(/\s+/g, " ").trim()}'`);
  }
  return lines.join("\n");
}

const selectedFunnel = computed(
  () => funnels.value.find((f) => f.id === selectedFunnelId.value) || null
);
const funnelStages = computed(() => {
  const f = selectedFunnel.value;
  if (!f) return [];
  return [...(f.stages || [])].sort((a, b) => a.position - b.position || a.id - b.id);
});

const showUserModal = ref(false);
const editingUserId = ref(null);
const userFormLoading = ref(false);
const userFormError = ref("");
const userActionError = ref("");
const userForm = reactive({
  username: "",
  password: "",
  full_name: "",
  email: "",
  bio: "",
  role: "creator",
  is_admin: false,
});

const newTeamName = ref("");
const newTeamLoading = ref(false);
const teamError = ref("");

const newPermission = reactive({ from_team_id: "", to_team_id: "" });
const permissionLoading = ref(false);
const permissionError = ref("");

const editingRuleId = ref(null);
const showRuleModal = ref(false);
const ruleLoading = ref(false);
const ruleError = ref("");
const ruleForm = reactive({
  name: "",
  enabled: true,
  trigger_type: "schedule",
  action_type: "create_task",
  schedule_interval: "daily",
  schedule_time: "09:00",
  schedule_weekday: 0,
  watch_from_stage_id: "",
  watch_to_stage_id: "",
  inactivity_days: 30,
  condition_no_stage_task: false,
  condition_stage_id: "",
  condition_client_id: "",
  condition_no_tasks: false,
  target_stage_id: "",
  move_from_stage_id: "",
  move_scope: "trigger_task",
  email_to_template: "{client_email}",
  title_template: "",
  description_template: "",
  creator_id: null,
  assignee_ids: [],
  observer_ids: [],
  due_offset_days: "",
  funnel_id: "",
  target_funnel_id: "",
});

const ruleStages = computed(() => {
  const fid = ruleForm.funnel_id ? Number(ruleForm.funnel_id) : null;
  const list = fid
    ? stages.value.filter((s) => s.funnel_id === fid)
    : stages.value;
  return [...list].sort((a, b) => a.position - b.position || a.id - b.id);
});

const actionStages = computed(() => {
  const fid = ruleForm.target_funnel_id
    ? Number(ruleForm.target_funnel_id)
    : ruleForm.funnel_id
      ? Number(ruleForm.funnel_id)
      : null;
  const list = fid
    ? stages.value.filter((s) => s.funnel_id === fid)
    : stages.value;
  return [...list].sort((a, b) => a.position - b.position || a.id - b.id);
});

const emailForm = reactive({
  smtp_host: "",
  smtp_port: 587,
  smtp_user: "",
  smtp_password: "",
  from_email: "",
  from_name: "Simple CRM",
  use_tls: true,
  use_ssl: false,
  imap_host: "",
  imap_port: 993,
  imap_user: "",
  imap_password: "",
  imap_use_ssl: true,
  imap_folder: "INBOX",
});
const emailLoading = ref(false);
const emailTestLoading = ref(false);
const emailError = ref("");
const emailOk = ref("");
const testTo = ref("");

function defaultRuleFunnelId() {
  const def = funnels.value.find((f) => f.is_default);
  return def?.id || funnels.value[0]?.id || "";
}

function funnelIdFromStageIds(...ids) {
  for (const id of ids) {
    if (!id) continue;
    const s = stages.value.find((x) => x.id === Number(id));
    if (s?.funnel_id) return s.funnel_id;
  }
  return defaultRuleFunnelId();
}

function syncRuleStagesToFunnel() {
  const list = ruleStages.value;
  const ids = new Set(list.map((s) => s.id));
  const first = list[0]?.id || "";

  if (ruleForm.watch_from_stage_id && !ids.has(Number(ruleForm.watch_from_stage_id))) {
    ruleForm.watch_from_stage_id = "";
  }
  if (!ruleForm.watch_to_stage_id || !ids.has(Number(ruleForm.watch_to_stage_id))) {
    ruleForm.watch_to_stage_id = first;
  }
  if (!ruleForm.condition_stage_id || !ids.has(Number(ruleForm.condition_stage_id))) {
    ruleForm.condition_stage_id = first;
  }
  if (!ruleForm.move_from_stage_id || !ids.has(Number(ruleForm.move_from_stage_id))) {
    ruleForm.move_from_stage_id = first;
  }
}

function syncActionStagesToTargetFunnel() {
  const list = actionStages.value;
  const ids = new Set(list.map((s) => s.id));
  const first = list[0]?.id || "";
  const second = list[1]?.id || first;

  if (ruleForm.action_type === "move_tasks") {
    if (!ruleForm.target_stage_id || !ids.has(Number(ruleForm.target_stage_id))) {
      ruleForm.target_stage_id = second || first;
    }
  } else if (ruleForm.action_type === "create_task") {
    if (ruleForm.target_stage_id && !ids.has(Number(ruleForm.target_stage_id))) {
      ruleForm.target_stage_id = first;
    }
  }
}

function emptyRuleForm() {
  ruleForm.name = "";
  ruleForm.enabled = true;
  ruleForm.trigger_type = "schedule";
  ruleForm.action_type = "create_task";
  ruleForm.schedule_interval = "daily";
  ruleForm.schedule_time = "09:00";
  ruleForm.schedule_weekday = 0;
  ruleForm.funnel_id = defaultRuleFunnelId();
  ruleForm.target_funnel_id = ruleForm.funnel_id;
  const list = ruleStages.value;
  const first = list[0]?.id || "";
  const second = list[1]?.id || first;
  ruleForm.watch_from_stage_id = "";
  ruleForm.watch_to_stage_id = first;
  ruleForm.inactivity_days = 30;
  ruleForm.condition_no_stage_task = false;
  ruleForm.condition_stage_id = first;
  ruleForm.condition_client_id = "";
  ruleForm.condition_no_tasks = false;
  ruleForm.target_stage_id = first;
  ruleForm.move_from_stage_id = first;
  ruleForm.move_scope = "trigger_task";
  ruleForm.email_to_template = "{client_email}";
  ruleForm.title_template = "";
  ruleForm.description_template = "";
  ruleForm.creator_id = users.value[0]?.id || null;
  ruleForm.assignee_ids = [];
  ruleForm.observer_ids = [];
  ruleForm.due_offset_days = "";
}

function resetRuleForm() {
  editingRuleId.value = null;
  ruleError.value = "";
  emptyRuleForm();
}

function openCreateRuleModal() {
  resetRuleForm();
  showRuleModal.value = true;
}

function closeRuleModal() {
  resetRuleForm();
  showRuleModal.value = false;
}

function editRule(rule) {
  editingRuleId.value = rule.id;
  showRuleModal.value = true;
  ruleForm.name = rule.name;
  ruleForm.enabled = rule.enabled;
  ruleForm.trigger_type =
    rule.trigger_type === "client_no_stage_task" ? "schedule" : rule.trigger_type;
  ruleForm.action_type = rule.action_type || "create_task";
  ruleForm.schedule_interval = rule.schedule_interval || "daily";
  ruleForm.schedule_time = utcToMsk(rule.schedule_time || "06:00");
  ruleForm.schedule_weekday = rule.schedule_weekday ?? 0;
  ruleForm.funnel_id = funnelIdFromStageIds(
    rule.watch_to_stage_id,
    rule.watch_from_stage_id,
    rule.move_from_stage_id,
    rule.condition_stage_id
  );
  ruleForm.target_funnel_id =
    funnelIdFromStageIds(rule.target_stage_id) || ruleForm.funnel_id;
  ruleForm.watch_from_stage_id = rule.watch_from_stage_id || "";
  ruleForm.watch_to_stage_id = rule.watch_to_stage_id || "";
  ruleForm.inactivity_days = rule.inactivity_days || 30;
  ruleForm.condition_no_stage_task = Boolean(
    rule.condition_no_stage_task || rule.trigger_type === "client_no_stage_task"
  );
  ruleForm.condition_stage_id = rule.condition_stage_id || "";
  ruleForm.condition_client_id = rule.condition_client_id || "";
  ruleForm.condition_no_tasks = Boolean(rule.condition_no_tasks);
  ruleForm.target_stage_id = rule.target_stage_id || "";
  ruleForm.move_from_stage_id = rule.move_from_stage_id || "";
  ruleForm.move_scope = rule.move_scope || "client_stage";
  ruleForm.email_to_template = rule.email_to_template || "{client_email}";
  ruleForm.title_template = rule.title_template;
  ruleForm.description_template = rule.description_template || "";
  ruleForm.creator_id = rule.creator_id;
  ruleForm.assignee_ids = [...(rule.assignee_ids || [])];
  ruleForm.observer_ids = [...(rule.observer_ids || [])];
  ruleForm.due_offset_days = rule.due_offset_days ?? "";
  syncRuleStagesToFunnel();
  syncActionStagesToTargetFunnel();
  activeSection.value = "automation";
}

watch(
  () => ruleForm.funnel_id,
  (id, prev) => {
    if (!id || id === prev) return;
    syncRuleStagesToFunnel();
  }
);

watch(
  () => ruleForm.target_funnel_id,
  (id, prev) => {
    if (!id || id === prev) return;
    syncActionStagesToTargetFunnel();
  }
);

watch(
  () => ruleForm.action_type,
  (type, prev) => {
    if (!type || type === prev) return;
    if (!ruleForm.target_funnel_id) {
      ruleForm.target_funnel_id = ruleForm.funnel_id;
    }
    syncActionStagesToTargetFunnel();
  }
);

function stageName(id) {
  const s = stages.value.find((x) => x.id === id);
  if (!s) return `#${id}`;
  const funnel = funnels.value.find((f) => f.id === s.funnel_id);
  return funnel ? `${s.name} (${funnel.name})` : s.name;
}

/** В БД schedule_time хранится как UTC; в UI показываем/вводим МСК (UTC+3). */
function shiftTimeHhMm(hhmm, hoursDelta) {
  const raw = String(hhmm || "09:00").trim();
  const m = raw.match(/^(\d{1,2}):(\d{2})$/);
  if (!m) return "09:00";
  let h = Number(m[1]) + hoursDelta;
  const min = Number(m[2]);
  h = ((h % 24) + 24) % 24;
  return `${String(h).padStart(2, "0")}:${String(min).padStart(2, "0")}`;
}
function utcToMsk(hhmm) {
  return shiftTimeHhMm(hhmm, 3);
}
function mskToUtc(hhmm) {
  return shiftTimeHhMm(hhmm, -3);
}

function triggerLabel(rule) {
  const type =
    rule.trigger_type === "client_no_stage_task" ? "schedule" : rule.trigger_type;
  if (type === "schedule") {
    const interval = rule.schedule_interval === "weekly" ? "еженедельно" : "ежедневно";
    return `${interval} в ${utcToMsk(rule.schedule_time || "06:00")} МСК`;
  }
  if (type === "client_inactive") {
    return `нет активности ${rule.inactivity_days || "?"} дн.`;
  }
  if (type === "client_email") {
    return "новое письмо от клиента";
  }
  const to = stageName(rule.watch_to_stage_id);
  if (rule.watch_from_stage_id) {
    return `стадия ${stageName(rule.watch_from_stage_id)} → ${to}`;
  }
  return `стадия → ${to}`;
}

function conditionsLabel(rule) {
  const parts = [];
  if (rule.condition_no_tasks) {
    parts.push("нет задач у клиента");
  }
  const noStage =
    rule.condition_no_stage_task || rule.trigger_type === "client_no_stage_task";
  if (noStage) {
    parts.push(`нет задач на «${stageName(rule.condition_stage_id)}»`);
  }
  if (rule.condition_client_id) {
    const name =
      clientsList.value.find((c) => c.id === rule.condition_client_id)?.name || "клиент";
    parts.push(`клиент ${name}`);
  }
  return parts.join(", ");
}

function actionLabel(rule) {
  const type = rule.action_type || "create_task";
  if (type === "send_email") return "отправить письмо";
  if (type === "move_tasks") return "переместить задачи";
  return "создать задачу";
}

function moveScopeLabel(scope) {
  if (scope === "trigger_task") return "задача из события";
  if (scope === "all_stage") return "все на стадии";
  return "задачи клиента";
}

function formatDate(iso) {
  return new Date(iso + (iso.endsWith("Z") ? "" : "Z")).toLocaleString("ru-RU");
}

function buildRulePayload() {
  const due =
    ruleForm.due_offset_days === "" || ruleForm.due_offset_days === null
      ? null
      : Number(ruleForm.due_offset_days);
  return {
    name: ruleForm.name,
    enabled: ruleForm.enabled,
    trigger_type: ruleForm.trigger_type,
    schedule_interval:
      ruleForm.trigger_type === "schedule" ? ruleForm.schedule_interval : null,
    schedule_time:
      ruleForm.trigger_type === "schedule"
        ? mskToUtc(ruleForm.schedule_time || "09:00")
        : ruleForm.schedule_time || "09:00",
    schedule_weekday:
      ruleForm.trigger_type === "schedule" && ruleForm.schedule_interval === "weekly"
        ? Number(ruleForm.schedule_weekday)
        : null,
    watch_from_stage_id:
      ruleForm.trigger_type === "status_change" && ruleForm.watch_from_stage_id
        ? Number(ruleForm.watch_from_stage_id)
        : null,
    watch_to_stage_id:
      ruleForm.trigger_type === "status_change" && ruleForm.watch_to_stage_id
        ? Number(ruleForm.watch_to_stage_id)
        : null,
    inactivity_days:
      ruleForm.trigger_type === "client_inactive"
        ? Number(ruleForm.inactivity_days)
        : null,
    condition_no_stage_task: Boolean(ruleForm.condition_no_stage_task),
    condition_stage_id:
      ruleForm.condition_no_stage_task && ruleForm.condition_stage_id
        ? Number(ruleForm.condition_stage_id)
        : null,
    condition_client_id: ruleForm.condition_client_id
      ? Number(ruleForm.condition_client_id)
      : null,
    condition_no_tasks: Boolean(ruleForm.condition_no_tasks),
    action_type: ruleForm.action_type,
    target_stage_id: (() => {
      if (ruleForm.action_type === "move_tasks") {
        return ruleForm.target_stage_id ? Number(ruleForm.target_stage_id) : null;
      }
      if (ruleForm.action_type !== "create_task") return null;
      if (ruleForm.target_stage_id) return Number(ruleForm.target_stage_id);
      const first = actionStages.value[0]?.id;
      return first ? Number(first) : null;
    })(),
    move_from_stage_id:
      ruleForm.action_type === "move_tasks" && ruleForm.move_from_stage_id
        ? Number(ruleForm.move_from_stage_id)
        : null,
    move_scope:
      ruleForm.action_type === "move_tasks"
        ? ruleForm.move_scope || "client_stage"
        : "client_stage",
    email_to_template:
      ruleForm.action_type === "send_email" ? ruleForm.email_to_template : "",
    title_template:
      ruleForm.action_type === "move_tasks" ? "" : ruleForm.title_template,
    description_template:
      ruleForm.action_type === "move_tasks" ? "" : ruleForm.description_template,
    creator_id: Number(ruleForm.creator_id),
    assignee_ids:
      ruleForm.action_type === "create_task" ? ruleForm.assignee_ids.map(Number) : [],
    observer_ids:
      ruleForm.action_type === "create_task" ? ruleForm.observer_ids.map(Number) : [],
    due_offset_days:
      ruleForm.action_type === "create_task" && Number.isFinite(due) ? due : null,
  };
}

function roleLabel(role) {
  if (role === "creator") return "Может ставить задачи";
  if (role === "executor") return "Исполнитель";
  if (role === "observer") return "Наблюдатель";
  return role;
}

async function saveRolePermission(rp) {
  rolePermLoading.value = rp.role;
  rolePermError.value = "";
  rolePermOk.value = "";
  try {
    const saved = await updateRolePermission(rp.role, {
      can_create: rp.can_create,
      can_edit: rp.can_edit,
      can_delete: rp.can_delete,
      can_edit_any: rp.can_edit_any,
      can_delete_any: rp.can_delete_any,
    });
    const idx = rolePermissions.value.findIndex((r) => r.role === saved.role);
    if (idx >= 0) rolePermissions.value[idx] = saved;
    rolePermOk.value = `Права роли «${roleLabel(saved.role)}» сохранены`;
  } catch (e) {
    rolePermError.value = e.response?.data?.detail || "Не удалось сохранить права роли";
  } finally {
    rolePermLoading.value = "";
  }
}

async function refreshAll() {
  const [u, t, p, rules, email, st, cl, tokens, rp, fn, fp, tpls] = await Promise.all([
    listAllUsers(),
    listTeams(),
    listPermissions(),
    listAutomationRules(),
    getEmailSettings(),
    listStages(),
    listClients(),
    listApiTokens(),
    listRolePermissions(),
    listFunnels(),
    listFunnelPermissions(),
    listMessageTemplates(),
  ]);
  users.value = u;
  teams.value = t;
  permissions.value = p;
  funnelPermissions.value = fp;
  rolePermissions.value = rp;
  automationRules.value = rules;
  apiTokens.value = tokens;
  messageTemplates.value = tpls;
  stages.value = st;
  funnels.value = fn;
  if (!selectedFunnelId.value || !fn.some((f) => f.id === selectedFunnelId.value)) {
    selectedFunnelId.value = fn[0]?.id || null;
  }
  if (!ruleForm.funnel_id || !fn.some((f) => f.id === Number(ruleForm.funnel_id))) {
    ruleForm.funnel_id = fn.find((f) => f.is_default)?.id || fn[0]?.id || "";
  }
  clientsList.value = cl;
  emailSettings.value = email;
  emailForm.smtp_host = email.smtp_host || "";
  emailForm.smtp_port = email.smtp_port || 587;
  emailForm.smtp_user = email.smtp_user || "";
  emailForm.smtp_password = "";
  emailForm.from_email = email.from_email || "";
  emailForm.from_name = email.from_name || "Simple CRM";
  emailForm.use_tls = email.use_tls;
  emailForm.use_ssl = email.use_ssl;
  emailForm.imap_host = email.imap_host || "";
  emailForm.imap_port = email.imap_port || 993;
  emailForm.imap_user = email.imap_user || "";
  emailForm.imap_password = "";
  emailForm.imap_use_ssl = email.imap_use_ssl !== false;
  emailForm.imap_folder = email.imap_folder || "INBOX";
  if (!ruleForm.creator_id && u.length) {
    ruleForm.creator_id = u[0].id;
  }
  if (!tokenForm.actor_user_id && u.length) {
    tokenForm.actor_user_id = u[0].id;
  }
}

async function submitApiToken() {
  tokenLoading.value = true;
  tokenError.value = "";
  try {
    const created = await createApiToken({
      name: tokenForm.name,
      actor_user_id: Number(tokenForm.actor_user_id),
    });
    createdTokenValue.value = created.token;
    tokenForm.name = "";
    await refreshAll();
  } catch (e) {
    tokenError.value = e.response?.data?.detail || "Не удалось создать токен";
  } finally {
    tokenLoading.value = false;
  }
}

async function copyCreatedToken() {
  if (!createdTokenValue.value) return;
  try {
    await navigator.clipboard.writeText(createdTokenValue.value);
  } catch {
    /* ignore */
  }
}

async function revokeToken(t) {
  if (!confirm(`Отозвать токен «${t.name}»?`)) return;
  await revokeApiToken(t.id);
  await refreshAll();
}

async function removeToken(t) {
  if (!confirm(`Удалить токен «${t.name}» безвозвратно?`)) return;
  await deleteApiToken(t.id);
  await refreshAll();
}

onMounted(refreshAll);

function nonMembers(team) {
  const memberIds = new Set(team.members.map((m) => m.id));
  return users.value.filter((u) => !memberIds.has(u.id));
}

function resetUserForm() {
  editingUserId.value = null;
  userForm.username = "";
  userForm.password = "";
  userForm.full_name = "";
  userForm.email = "";
  userForm.bio = "";
  userForm.role = "creator";
  userForm.is_admin = false;
  userFormError.value = "";
}

function openCreateUser() {
  resetUserForm();
  showUserModal.value = true;
}

function openEditUser(u) {
  editingUserId.value = u.id;
  userForm.username = u.username || "";
  userForm.password = "";
  userForm.full_name = u.full_name || "";
  userForm.email = u.email || "";
  userForm.bio = u.bio || "";
  userForm.role = u.role || "creator";
  userForm.is_admin = !!u.is_admin;
  userFormError.value = "";
  showUserModal.value = true;
}

function closeUserModal() {
  showUserModal.value = false;
  resetUserForm();
}

async function submitUserForm() {
  userFormError.value = "";
  userActionError.value = "";
  const username = userForm.username.trim();
  const full_name = userForm.full_name.trim();
  if (!username || !full_name) {
    userFormError.value = "Логин и имя обязательны";
    return;
  }
  if (!editingUserId.value && !userForm.password) {
    userFormError.value = "Укажите пароль";
    return;
  }
  userFormLoading.value = true;
  try {
    const payload = {
      username,
      full_name,
      email: userForm.email.trim(),
      bio: userForm.bio,
      role: userForm.role,
      is_admin: !!userForm.is_admin,
    };
    if (editingUserId.value) {
      if (userForm.password) payload.password = userForm.password;
      await updateUser(editingUserId.value, payload);
    } else {
      payload.password = userForm.password;
      await createUser(payload);
    }
    closeUserModal();
    await refreshAll();
  } catch (e) {
    userFormError.value =
      e.response?.data?.detail ||
      (editingUserId.value
        ? "Не удалось сохранить пользователя"
        : "Не удалось создать пользователя");
  } finally {
    userFormLoading.value = false;
  }
}

function resetTemplateForm() {
  editingTemplateId.value = null;
  templateForm.name = "";
  templateForm.subject_template = "";
  templateForm.body_template = "";
  templateFormError.value = "";
}

function openCreateMessageTemplate() {
  resetTemplateForm();
  showTemplateModal.value = true;
}

function editMessageTemplate(t) {
  editingTemplateId.value = t.id;
  templateForm.name = t.name || "";
  templateForm.subject_template = t.subject_template || "";
  templateForm.body_template = t.body_template || "";
  templateFormError.value = "";
  showTemplateModal.value = true;
}

function closeTemplateModal() {
  showTemplateModal.value = false;
  resetTemplateForm();
}

async function submitMessageTemplate() {
  templateFormError.value = "";
  templateError.value = "";
  const name = templateForm.name.trim();
  if (!name) {
    templateFormError.value = "Название обязательно";
    return;
  }
  templateLoading.value = true;
  try {
    const payload = {
      name,
      subject_template: templateForm.subject_template,
      body_template: templateForm.body_template,
    };
    if (editingTemplateId.value) {
      await updateMessageTemplate(editingTemplateId.value, payload);
    } else {
      await createMessageTemplate(payload);
    }
    closeTemplateModal();
    await refreshAll();
  } catch (e) {
    templateFormError.value =
      e.response?.data?.detail || "Не удалось сохранить шаблон";
  } finally {
    templateLoading.value = false;
  }
}

async function removeMessageTemplate(t) {
  templateError.value = "";
  if (!confirm(`Удалить шаблон «${t.name}»?`)) return;
  try {
    await deleteMessageTemplate(t.id);
    await refreshAll();
  } catch (e) {
    templateError.value = e.response?.data?.detail || "Не удалось удалить шаблон";
  }
}

async function submitNewTeam() {
  teamError.value = "";
  newTeamLoading.value = true;
  try {
    await createTeam(newTeamName.value.trim());
    newTeamName.value = "";
    await refreshAll();
  } catch (e) {
    teamError.value = e.response?.data?.detail || "Не удалось создать команду";
  } finally {
    newTeamLoading.value = false;
  }
}

async function removeUser(user) {
  userActionError.value = "";
  if (!confirm(`Удалить пользователя «${user.full_name}»?`)) return;
  try {
    await deleteUser(user.id);
    await refreshAll();
  } catch (e) {
    userActionError.value = e.response?.data?.detail || "Не удалось удалить пользователя";
  }
}

async function removeTeam(team) {
  teamError.value = "";
  if (!confirm(`Удалить команду «${team.name}»?`)) return;
  try {
    await deleteTeam(team.id);
    await refreshAll();
  } catch (e) {
    teamError.value = e.response?.data?.detail || "Не удалось удалить команду";
  }
}

async function onAddMember(team, event) {
  const userId = Number(event.target.value);
  event.target.value = "";
  if (!userId) return;
  teamError.value = "";
  try {
    await addTeamMember(team.id, userId);
    await refreshAll();
  } catch (e) {
    teamError.value = e.response?.data?.detail || "Не удалось добавить участника";
  }
}

async function removeMember(team, user) {
  teamError.value = "";
  try {
    await removeTeamMember(team.id, user.id);
    await refreshAll();
  } catch (e) {
    teamError.value = e.response?.data?.detail || "Не удалось убрать участника";
  }
}

async function submitNewPermission() {
  permissionError.value = "";
  if (!newPermission.from_team_id || !newPermission.to_team_id) return;
  permissionLoading.value = true;
  try {
    await createPermission(newPermission.from_team_id, newPermission.to_team_id);
    newPermission.from_team_id = "";
    newPermission.to_team_id = "";
    await refreshAll();
  } catch (e) {
    permissionError.value = e.response?.data?.detail || "Не удалось добавить право";
  } finally {
    permissionLoading.value = false;
  }
}

async function removePermission(p) {
  await deletePermission(p.id);
  await refreshAll();
}

async function submitFunnelPermission() {
  funnelPermError.value = "";
  if (!newFunnelPermission.team_id || !newFunnelPermission.funnel_id) return;
  funnelPermLoading.value = true;
  try {
    await createFunnelPermission(
      Number(newFunnelPermission.team_id),
      Number(newFunnelPermission.funnel_id)
    );
    newFunnelPermission.team_id = "";
    newFunnelPermission.funnel_id = "";
    await refreshAll();
  } catch (e) {
    funnelPermError.value =
      e.response?.data?.detail || "Не удалось добавить видимость воронки";
  } finally {
    funnelPermLoading.value = false;
  }
}

async function removeFunnelPermission(p) {
  await deleteFunnelPermission(p.id);
  await refreshAll();
}

function resetFunnelForm() {
  editingFunnelId.value = null;
  funnelForm.name = "";
  funnelForm.team_id = "";
  funnelForm.is_default = false;
  funnelError.value = "";
}

function editFunnel(f) {
  editingFunnelId.value = f.id;
  funnelForm.name = f.name;
  funnelForm.team_id = f.team_id != null ? f.team_id : "";
  funnelForm.is_default = !!f.is_default;
  funnelError.value = "";
  selectedFunnelId.value = f.id;
}

async function submitFunnelForm() {
  funnelError.value = "";
  const name = funnelForm.name.trim();
  if (!name) {
    funnelError.value = "Название обязательно";
    return;
  }
  const team_id = funnelForm.team_id ? Number(funnelForm.team_id) : null;
  funnelLoading.value = true;
  try {
    if (editingFunnelId.value) {
      await updateFunnel(editingFunnelId.value, {
        name,
        team_id,
        is_default: funnelForm.is_default || undefined,
      });
      const id = editingFunnelId.value;
      resetFunnelForm();
      await refreshAll();
      selectedFunnelId.value = id;
    } else {
      const created = await createFunnel({
        name,
        team_id,
        is_default: funnelForm.is_default,
        with_default_stages: true,
      });
      resetFunnelForm();
      await refreshAll();
      selectedFunnelId.value = created.id;
    }
  } catch (e) {
    funnelError.value =
      e.response?.data?.detail ||
      (editingFunnelId.value
        ? "Не удалось сохранить воронку"
        : "Не удалось создать воронку");
  } finally {
    funnelLoading.value = false;
  }
}

async function makeFunnelDefault(f) {
  funnelError.value = "";
  try {
    await updateFunnel(f.id, { is_default: true });
    await refreshAll();
  } catch (e) {
    funnelError.value =
      e.response?.data?.detail || "Не удалось назначить воронку по умолчанию";
  }
}

async function removeFunnel(f) {
  funnelError.value = "";
  if (!confirm(`Удалить воронку «${f.name}» и её стадии?`)) return;
  try {
    await deleteFunnel(f.id);
    if (selectedFunnelId.value === f.id) selectedFunnelId.value = null;
    await refreshAll();
  } catch (e) {
    funnelError.value = e.response?.data?.detail || "Не удалось удалить воронку";
  }
}

function onFunnelDragStart(idx) {
  dragFunnelIndex.value = idx;
}

async function onFunnelDrop(idx) {
  const from = dragFunnelIndex.value;
  dragFunnelIndex.value = null;
  if (from === null || from === idx) return;
  const list = [...funnels.value];
  const [item] = list.splice(from, 1);
  list.splice(idx, 0, item);
  funnels.value = list.map((f, i) => ({ ...f, position: i }));
  funnelError.value = "";
  try {
    await reorderFunnels(list.map((f) => f.id));
    await refreshAll();
  } catch (e) {
    funnelError.value = e.response?.data?.detail || "Не удалось изменить порядок воронок";
    await refreshAll();
  }
}

function onStageDragStart(idx) {
  dragStageIndex.value = idx;
}

async function onStageDrop(idx) {
  const from = dragStageIndex.value;
  dragStageIndex.value = null;
  if (from === null || from === idx || !selectedFunnelId.value) return;
  const list = [...funnelStages.value];
  const [item] = list.splice(from, 1);
  list.splice(idx, 0, item);
  const funnel = funnels.value.find((f) => f.id === selectedFunnelId.value);
  if (funnel) {
    funnel.stages = list.map((s, i) => ({ ...s, position: i }));
  }
  stageError.value = "";
  try {
    await reorderStages(
      list.map((s) => s.id),
      selectedFunnelId.value
    );
    await refreshAll();
  } catch (e) {
    stageError.value = e.response?.data?.detail || "Не удалось изменить порядок";
    await refreshAll();
  }
}

async function submitNewStage() {
  if (!selectedFunnelId.value) {
    stageError.value = "Сначала выберите воронку";
    return;
  }
  stageError.value = "";
  stageLoading.value = true;
  try {
    await createStage({
      name: newStageName.value.trim(),
      funnel_id: selectedFunnelId.value,
    });
    newStageName.value = "";
    await refreshAll();
  } catch (e) {
    stageError.value = e.response?.data?.detail || "Не удалось создать стадию";
  } finally {
    stageLoading.value = false;
  }
}

async function saveStageName(stage) {
  stageError.value = "";
  try {
    await updateStage(stage.id, { name: stage.name });
    await refreshAll();
  } catch (e) {
    stageError.value = e.response?.data?.detail || "Не удалось сохранить";
  }
}

async function saveStageFlags(stage) {
  stageError.value = "";
  try {
    await updateStage(stage.id, {
      assignee_can_set: stage.assignee_can_set,
      requires_result: stage.requires_result,
      is_final: stage.is_final,
    });
  } catch (e) {
    stageError.value = e.response?.data?.detail || "Не удалось сохранить";
    await refreshAll();
  }
}

async function removeStage(stage) {
  if (!confirm(`Удалить стадию «${stage.name}»?`)) return;
  stageError.value = "";
  try {
    await deleteStage(stage.id);
    await refreshAll();
  } catch (e) {
    stageError.value = e.response?.data?.detail || "Не удалось удалить стадию";
  }
}

async function submitRule() {
  ruleError.value = "";
  ruleLoading.value = true;
  try {
    const payload = buildRulePayload();
    if (editingRuleId.value) {
      await updateAutomationRule(editingRuleId.value, payload);
    } else {
      await createAutomationRule(payload);
    }
    closeRuleModal();
    await refreshAll();
  } catch (e) {
    ruleError.value = e.response?.data?.detail || "Не удалось сохранить правило";
  } finally {
    ruleLoading.value = false;
  }
}

async function removeRule(rule) {
  if (!confirm(`Удалить правило «${rule.name}»?`)) return;
  await deleteAutomationRule(rule.id);
  if (editingRuleId.value === rule.id) closeRuleModal();
  await refreshAll();
}

async function submitEmailSettings() {
  emailError.value = "";
  emailOk.value = "";
  emailLoading.value = true;
  try {
    const payload = {
      smtp_host: emailForm.smtp_host,
      smtp_port: emailForm.smtp_port,
      smtp_user: emailForm.smtp_user,
      from_email: emailForm.from_email,
      from_name: emailForm.from_name,
      use_tls: emailForm.use_tls,
      use_ssl: emailForm.use_ssl,
      imap_host: emailForm.imap_host,
      imap_port: emailForm.imap_port,
      imap_user: emailForm.imap_user,
      imap_use_ssl: emailForm.imap_use_ssl,
      imap_folder: emailForm.imap_folder,
    };
    if (emailForm.smtp_password) {
      payload.smtp_password = emailForm.smtp_password;
    }
    if (emailForm.imap_password) {
      payload.imap_password = emailForm.imap_password;
    } else {
      payload.smtp_password = null;
    }
    const saved = await saveEmailSettings(payload);
    emailSettings.value = saved;
    emailForm.smtp_password = "";
    emailForm.imap_password = "";
    emailOk.value = "Настройки сохранены";
  } catch (e) {
    emailError.value = e.response?.data?.detail || "Не удалось сохранить настройки";
  } finally {
    emailLoading.value = false;
  }
}

async function sendTestEmail() {
  emailError.value = "";
  emailOk.value = "";
  emailTestLoading.value = true;
  try {
    await testEmail(testTo.value.trim());
    emailOk.value = "Тестовое письмо отправлено";
  } catch (e) {
    emailError.value = e.response?.data?.detail || "Не удалось отправить тестовое письмо";
  } finally {
    emailTestLoading.value = false;
  }
}
</script>

<style scoped>
.admin-page {
  padding: 24px;
  max-width: 900px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

header {
  display: flex;
  align-items: center;
  gap: 16px;
}

.back-link {
  color: var(--primary);
  font-size: 13px;
  text-decoration: none;
}

h1 {
  font-size: 20px;
  margin: 0;
}

h3 {
  font-size: 14px;
  margin: 8px 0 0;
}

.admin-nav {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.nav-tab {
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text-muted);
  padding: 7px 12px;
  border-radius: 16px;
  font-size: 13px;
  font-weight: 600;
}

.nav-tab.active {
  background: var(--primary);
  border-color: var(--primary);
  color: white;
}

.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

h2 {
  font-size: 15px;
  margin: 0;
}

.hint {
  margin: -8px 0 0;
  font-size: 12px;
  color: var(--text-muted);
}

.hint code {
  background: var(--bg);
  padding: 1px 5px;
  border-radius: 4px;
}

.users-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.users-table th {
  text-align: left;
  color: var(--text-muted);
  font-size: 11px;
  text-transform: uppercase;
  padding: 4px 8px;
  border-bottom: 1px solid var(--border);
}

.users-table td {
  padding: 6px 8px;
  border-bottom: 1px solid var(--border);
}

.admin-tag {
  background: #6554c0;
  color: white;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 8px;
  margin-left: 6px;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: var(--bg);
  border: 1px solid var(--border);
  padding: 2px 9px;
  border-radius: 12px;
  font-size: 12px;
  margin-right: 4px;
}

.chip.removable {
  padding-right: 4px;
}

.chip-remove {
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: 14px;
  line-height: 1;
  padding: 0 2px;
}

.chip-remove:hover {
  color: var(--danger);
}

.muted {
  color: var(--text-muted);
  font-size: 12px;
}

.inline-form {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.inline-form input,
.inline-form select,
.stack-form input,
.stack-form select,
.stack-form textarea {
  padding: 7px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 13px;
  font-family: inherit;
}

.stack-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.stack-form label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
}

.stack-form .checkbox-row {
  flex-direction: row;
  align-items: center;
  gap: 8px;
  font-weight: 500;
  color: var(--text);
}

.multi {
  min-height: 90px;
}

.teams-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.team-block,
.rule-block {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.team-header,
.rule-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.rule-actions {
  display: flex;
  gap: 10px;
}

.rule-meta {
  font-size: 12px;
  color: var(--text-muted);
}

.form-section-title {
  margin: 12px 0 0;
  font-size: 14px;
  font-weight: 600;
}

.token-reveal {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  padding: 12px;
  margin-bottom: 14px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-elevated, #f7f7f8);
}

.token-value {
  word-break: break-all;
  font-size: 12px;
}

.api-auth-example {
  margin: 12px 0 16px;
}

.api-example {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0 12px 12px;
  margin-bottom: 10px;
  background: #fff;
}

.api-example summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  cursor: pointer;
  padding: 12px 0;
  list-style: none;
  user-select: none;
}

.api-example summary::-webkit-details-marker {
  display: none;
}

.api-example summary::before {
  content: "▸";
  color: #6b778c;
  font-size: 12px;
}

.api-example[open] summary::before {
  content: "▾";
}

.api-method {
  display: inline-block;
  min-width: 52px;
  text-align: center;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.03em;
  padding: 2px 6px;
  border-radius: 4px;
  color: #fff;
  background: #6b778c;
}

.api-method.get {
  background: #0b6e4f;
}

.api-method.post {
  background: #0052cc;
}

.api-method.put {
  background: #b76e00;
}

.api-method.delete {
  background: #de350b;
}

.api-desc {
  margin: 0 0 10px;
  font-size: 13px;
  color: var(--text-muted);
}

.api-example-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #6b778c;
  margin: 10px 0 4px;
}

.api-code {
  margin: 0;
  padding: 10px 12px;
  border-radius: 6px;
  background: #172b4d;
  color: #ebecf0;
  font-size: 12px;
  line-height: 1.45;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.member-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.add-member {
  display: flex;
  gap: 8px;
}

.link-btn {
  border: none;
  background: transparent;
  color: var(--primary);
  font-size: 12px;
  padding: 0;
}

.link-btn.danger {
  color: var(--danger);
}

.link-btn:hover {
  text-decoration: underline;
}

.permissions-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.permission-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.arrow {
  color: var(--text-muted);
}

.badge {
  font-size: 10px;
  padding: 1px 7px;
  border-radius: 8px;
  margin-left: 6px;
  text-transform: uppercase;
}

.badge.on {
  background: #e3fcef;
  color: #006644;
}

.badge.off {
  background: #f4f5f7;
  color: #6b778c;
}

.status-line {
  font-size: 13px;
}

.status-line .ok {
  color: #00875a;
  font-weight: 600;
}

.status-line .warn {
  color: #974f00;
  font-weight: 600;
}

.ok-text {
  color: #00875a;
  font-size: 13px;
  margin: 0;
}

.funnel-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 12px 0 16px;
}

.funnel-block {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  cursor: grab;
  background: #fff;
}

.funnel-block:active {
  cursor: grabbing;
}

.funnel-block.active {
  border-color: #2684ff;
  box-shadow: 0 0 0 1px #2684ff;
}

.funnel-block-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.stage-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
  cursor: grab;
}

.stage-row:active {
  cursor: grabbing;
}

.drag-handle {
  color: #6b778c;
  letter-spacing: -2px;
  user-select: none;
  font-size: 14px;
}

.stage-row input[type="text"],
.stage-row > input:not([type="checkbox"]) {
  flex: 1;
  min-width: 140px;
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
}

.overlay {
  position: fixed;
  inset: 0;
  background: rgba(9, 30, 66, 0.54);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  z-index: 50;
  padding: 24px;
  overflow-y: auto;
}

.rule-modal {
  background: var(--surface);
  border-radius: 10px;
  padding: 24px;
  width: min(560px, 100%);
  margin: 24px 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  box-shadow: 0 8px 24px rgba(9, 30, 66, 0.18);
}

.rule-modal h3 {
  margin: 0 0 4px;
}
</style>
