from langchain_gigachat import GigaChat
from langchain.prompts.chat import ChatPromptTemplate
from langchain_core.runnables import RunnableSequence
from langchain.schema import HumanMessage, AIMessage
from langchain_core.chat_history import InMemoryChatMessageHistory


TOKEN = ''

llm = GigaChat(credentials=TOKEN, verify_ssl_certs=False)

main_prompt = ChatPromptTemplate.from_template(
    '''
        Ты являешься HR-консультантом компании ЭПФ. Твоя задача - помогать людям с вопросами карьеры, вакансий и работы в компании ЭПФ.

        Тебе доступен список вакансий:
        {vacancies_list}

        АЛГОРИТМ РАБОТЫ:
        1. Проанализируй вопрос пользователя и определи, можно ли его интерпретировать в контексте работы в компании ЭПФ
        2. Если вопрос можно связать с карьерой, вакансиями или работой в ЭПФ - дай развернутый ответ в этом контексте
        3. Если вопрос НЕЛЬЗЯ никак связать с работой в ЭПФ - вежливо откажись отвечать

        КРИТЕРИИ ИНТЕРПРЕТАЦИИ:
        - Вопросы о навыках (Python, AI, программирование и т.д.) → можно интерпретировать как запрос о подходящих вакансиях в ЭПФ
        - Вопросы о образовании, опыте работы → можно интерпретировать как карьерную консультацию для работы в ЭПФ
        - Вопросы о технологиях, используемых в ЭПФ → прямо касаются рабочих процессов компании
        - Вопросы о личных качествах → можно интерпретировать как подготовку к собеседованию в ЭПФ

        ПРИМЕРЫ КОРРЕКТНОЙ ИНТЕРПРЕТАЦИИ:
        - "Я владею Python. Какие вакансии подойдут?" → "В ЭПФ востребованы специалисты, обладающие навыками программирования на Python для автоматизации процессов и обработки данных."
        - "Имею опыт в управлении проектами" → "ЭПФ ищет руководителей проектов для координации разработок новых продуктов и масштабирования производственных линий."
        - "Опыт в химической отрасли"→ "Для вас открыты вакансии химика-технолога и специалиста по антикоррозионным покрытиям в ЭПФ."
        
        ПРИМЕРЫ ОТКАЗА:
        - "Что такое компьютер?" → нельзя интерпретировать в контексте работы в ЭПФ
        - "Как приготовить борщ?" → нельзя интерпретировать в контексте работы в ЭПФ
        - "Что такое квантовая физика?" → нельзя интерпретировать в контексте работы в ЭПФ

        ПРАВИЛА ОТВЕТА:
        - Отвечай сразу по сути, без вводных фраз
        - Не пиши "Анализ вопроса", "Интерпретация" и т.д.
        - Не объясняй ход своих мыслей
        - Только конкретный и информативный ответ на вопрос
        - Подбирай подходящую вакансию только из списка выше
        - Если вакансия "Занято" — её нельзя предлагать
        - Если в списке нет вакансии, подходящей под описание пользователя, ответь: "У нас нет подходящей вакансии, соответствующей вашему описанию"
        - Всегда обязательно уточняй доступна ли подходящая вакансия в данный момент или нет.
        - При необходимости дальнейшей консультации предложи продолжить обсуждение в этом чате
        - Не предлагай конкретных способов связи с HR кроме продолжения диалога в этом интерфейсе

        Всегда старайся найти связь с работой в ЭПФ, если это возможно. Отказывай только если связь действительно отсутствует.

        История диалога: {chat_history}
        Пользователь: {user_input}
        HR-консультант:
    '''
)

classification_prompt = ChatPromptTemplate.from_template(
    '''
        Определи тип запроса пользователя. Возможные типы:
        1. "vacancies_list" - пользователь спрашивает о наличии/списке вакансий в компании ЭПФ
        3. "other" - все остальные запросы

        Верни ТОЛЬКО одно слово: "vacancies_list", "vacancy_help" или "other"

        Примеры:
        - "Какие вакансии есть в ЭПФ?" → vacancies_list
        - "Есть ли открытые вакансии?" → vacancies_list
        - "Как записаться на вакансию?" → vacancies_list
        - "Как подать заявку на работу?" → vacancies_list
        - "Что такое Python?" → other

        Запрос: {user_input}
        Тип:
    '''
)

classification_chain = RunnableSequence(classification_prompt | llm)
main_chain = RunnableSequence(main_prompt | llm)
user_memory = {}


def classify_intent(user_input: str):
    response_obj = classification_chain.invoke({"user_input": user_input})
    response_text = response_obj.content.strip().lower()

    if "vacancies_list" in response_text:
        return "vacancies_list"
    else:
        return user_input


def get_response(user_id: int, user_input: str, vacancies: list[list[str]]):
    intent = classify_intent(user_input)

    if intent == "vacancies_list":
        return "/vacancies"

    if user_id not in user_memory:
        user_memory[user_id] = InMemoryChatMessageHistory()

    memory = user_memory[user_id]

    chat_history = ""
    for message in memory.messages:
        if isinstance(message, HumanMessage):
            chat_history += f"Пользователь: {message.content}\n"
        elif isinstance(message, AIMessage):
            chat_history += f"HR-консультант: {message.content}\n"

    variables = {
        "user_input": user_input,
        "chat_history": chat_history,
        "vacancies_list": vacancies,
    }

    response_obj = main_chain.invoke(variables)
    response_text = response_obj.content

    memory.add_message(HumanMessage(content=user_input))
    memory.add_message(AIMessage(content=response_text))

    return response_text
