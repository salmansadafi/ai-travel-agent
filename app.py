# pylint: disable = invalid-name
import json
import os
import re
import uuid

import streamlit as st
from langchain_core.messages import HumanMessage, ToolMessage

from agents.agent import Agent

PERSIAN_TEXT_RE = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]')


def is_persian_text(text):
    return isinstance(text, str) and bool(PERSIAN_TEXT_RE.search(text))


def populate_envs(sender_email, receiver_email, subject):
    os.environ['FROM_EMAIL'] = sender_email
    os.environ['TO_EMAIL'] = receiver_email
    os.environ['EMAIL_SUBJECT'] = subject


def send_email(sender_email, receiver_email, subject, thread_id):
    try:
        populate_envs(sender_email, receiver_email, subject)
        config = {'configurable': {'thread_id': thread_id}}
        st.session_state.agent.graph.invoke(None, config=config)
        st.success('Email sent successfully!')
        # Clear session state
        for key in ['travel_info', 'thread_id']:
            st.session_state.pop(key, None)
    except Exception as e:
        st.error(f'Error sending email: {e}')


def initialize_agent():
    if 'agent' not in st.session_state:
        st.session_state.agent = Agent()


def _flight_summary(flight):
    segments = flight.get('flights', [])
    if not segments:
        return 'Flight details are unavailable.'

    first = segments[0]
    last = segments[-1]
    departure = first.get('departure_airport', {})
    arrival = last.get('arrival_airport', {})
    airlines = ', '.join(dict.fromkeys(
        segment.get('airline', '') for segment in segments if segment.get('airline')
    ))
    flight_numbers = ', '.join(
        segment.get('flight_number', '') for segment in segments if segment.get('flight_number')
    )
    summary = (
        f"**{departure.get('name', departure.get('id', 'Departure'))} → "
        f"{arrival.get('name', arrival.get('id', 'Arrival'))}**  \n"
        f"{airlines or 'Airline unavailable'}"
    )
    if flight_numbers:
        summary += f' · {flight_numbers}'
    if departure.get('time') and arrival.get('time'):
        summary += f"  \n{departure['time']} → {arrival['time']}"
    if flight.get('total_duration'):
        summary += f" · {flight['total_duration']} min"
    if flight.get('price') is not None:
        summary += f"  \n**Price:** ${flight['price']}"
    return summary


def _render_flight_leg(flight):
    segments = flight.get('flights', [])
    if segments and segments[0].get('airline_logo'):
        st.image(segments[0]['airline_logo'], width=70)
    st.markdown(_flight_summary(flight))


def _render_flight_results(data):
    st.subheader('✈️ Flight options')
    if isinstance(data, str):
        st.warning(data)
        return
    if data.get('error'):
        st.warning(data['error'])
        return

    trip_options = data.get('trip_options', [])
    if trip_options:
        st.caption('Each return option is matched to the outbound flight in the same card.')
        for index, trip in enumerate(trip_options, start=1):
            with st.container(border=True):
                st.markdown(f'#### Complete trip option {index}')
                outbound_col, return_col = st.columns(2)
                with outbound_col:
                    st.markdown('**Outbound**')
                    _render_flight_leg(trip.get('outbound_flight', {}))
                with return_col:
                    st.markdown('**Return**')
                    returns = trip.get('return_flights', [])
                    if returns:
                        _render_flight_leg(returns[0])
                        if len(returns) > 1:
                            with st.expander(f'{len(returns) - 1} more return choices'):
                                for flight in returns[1:]:
                                    _render_flight_leg(flight)
                                    st.divider()
                    else:
                        st.warning(
                            trip.get('warning', 'No return flight was found for this outbound option.')
                        )
        return

    outbound_flights = data.get('outbound_flights', [])
    if outbound_flights:
        for index, flight in enumerate(outbound_flights, start=1):
            st.markdown(f'**Outbound option {index}**')
            _render_flight_leg(flight)
            st.divider()
    else:
        st.info('No flight options were returned.')


def _hotel_image(hotel):
    if hotel.get('thumbnail'):
        return hotel['thumbnail']
    for image in hotel.get('images', []):
        if isinstance(image, dict):
            url = image.get('thumbnail') or image.get('original_image')
            if url:
                return url
    return None


def _render_hotel_results(hotels):
    st.subheader('🏨 Hotel options')
    if isinstance(hotels, str):
        st.warning(hotels)
        return
    if not hotels:
        st.info('No hotel options were returned.')
        return

    columns = st.columns(2)
    for index, hotel in enumerate(hotels):
        with columns[index % len(columns)]:
            with st.container(border=True):
                image = _hotel_image(hotel)
                if image:
                    st.image(image, use_column_width=True)
                st.markdown(f"### {hotel.get('name', 'Hotel')}")
                rating = hotel.get('overall_rating')
                if rating is not None:
                    reviews = hotel.get('reviews')
                    review_text = f' · {reviews:,} reviews' if isinstance(reviews, int) else ''
                    st.write(f'⭐ {rating}/5{review_text}')
                rate = hotel.get('rate_per_night', {})
                total = hotel.get('total_rate', {})
                nightly = rate.get('lowest') if isinstance(rate, dict) else None
                total_price = total.get('lowest') if isinstance(total, dict) else None
                if nightly:
                    st.write(f'**Per night:** {nightly}')
                if total_price:
                    st.write(f'**Total stay:** {total_price}')
                coordinates = hotel.get('gps_coordinates', {})
                if coordinates.get('latitude') is not None and coordinates.get('longitude') is not None:
                    map_url = (
                        'https://www.google.com/maps/search/?api=1&query='
                        f'{coordinates["latitude"]},{coordinates["longitude"]}'
                    )
                    st.link_button('View location', map_url)


def _render_tool_results(messages):
    for message in messages:
        if not isinstance(message, ToolMessage):
            continue
        try:
            data = json.loads(message.content)
        except (TypeError, json.JSONDecodeError):
            data = message.content
        if message.name == 'flights_finder':
            _render_flight_results(data)
        elif message.name == 'hotels_finder':
            _render_hotel_results(data)


def render_custom_css(user_input=''):
    is_rtl = is_persian_text(user_input)
    direction = 'rtl' if is_rtl else 'ltr'
    alignment = 'right' if is_rtl else 'left'
    st.markdown(
        f'''
        <style>
        .main-title {{
            font-size: 2.5em;
            color: #333;
            text-align: center;
            margin-bottom: 0.5em;
            font-weight: bold;
        }}
        .sub-title {{
            font-size: 1.2em;
            color: #333;
            text-align: {alignment};
            margin-bottom: 0.5em;
            direction: {direction};
        }}
        .center-container {{
            display: flex;
            flex-direction: column;
            align-items: center;
            width: 100%;
        }}
        .query-box {{
            width: 80%;
            max-width: 600px;
            margin-top: 0.5em;
            margin-bottom: 1em;
        }}
        .query-container {{
            width: 80%;
            max-width: 600px;
            margin: 0 auto;
        }}
        div[data-testid="stAppViewContainer"],
        .stApp, .stApp > div, .stMain, .stMarkdownContainer, .stTextArea textarea, .stTextInput input, .stSelectbox div, .stRadio div {{
            direction: {direction};
            text-align: {alignment};
        }}
        .stTextArea textarea, .stTextInput input {{
            text-align: {alignment};
        }}
        </style>
        ''', unsafe_allow_html=True)


def render_ui():
    is_rtl = is_persian_text(st.session_state.get('query', ''))
    st.markdown('<div class="center-container">', unsafe_allow_html=True)
    st.markdown('<div class="main-title">✈️🌍 AI Travel Agent 🏨🗺️</div>', unsafe_allow_html=True)
    st.markdown('<div class="query-container">', unsafe_allow_html=True)
    sub_title = 'درخواست سفر خود را بنویسید و اطلاعات پرواز و هتل را دریافت کنید:'
    if not is_rtl:
        sub_title = 'Enter your travel query and get flight and hotel information:'

    st.markdown(f'<div class="sub-title">{sub_title}</div>', unsafe_allow_html=True)
    with st.form(key='travel_query_form'):
        user_input = st.text_area(
            'Travel Query / درخواست سفر',
            height=200,
            key='query',
            placeholder='Type your travel query here... / توضیح سفر خود را اینجا بنویسید...',
        )
        submitted = st.form_submit_button('Get Travel Information / دریافت اطلاعات سفر')
    st.markdown('</div>', unsafe_allow_html=True)
    st.sidebar.image('images/ai-travel.png', caption='AI Travel Assistant')

    return user_input, submitted


def process_query(user_input):
    if user_input:
        try:
            thread_id = str(uuid.uuid4())
            st.session_state.thread_id = thread_id

            messages = [HumanMessage(content=user_input)]
            config = {'configurable': {'thread_id': thread_id}}

            result = st.session_state.agent.graph.invoke({'messages': messages}, config=config)

            st.subheader('Travel Information')
            final_message = result['messages'][-1]
            st.markdown(final_message.content)
            _render_tool_results(result['messages'])

            st.session_state.travel_info = final_message.content

        except Exception as e:
            st.error(f'Error: {e}')
    else:
        st.error('Please enter a travel query.')


def render_email_form():
    send_email_option = st.radio('Do you want to send this information via email?', ('No', 'Yes'))
    if send_email_option == 'Yes':
        with st.form(key='email_form'):
            sender_email = st.text_input('Sender Email')
            receiver_email = st.text_input('Receiver Email')
            subject = st.text_input('Email Subject', 'Travel Information')
            submit_button = st.form_submit_button(label='Send Email')

        if submit_button:
            if sender_email and receiver_email and subject:
                send_email(sender_email, receiver_email, subject, st.session_state.thread_id)
            else:
                st.error('Please fill out all email fields.')


def main():
    initialize_agent()
    render_custom_css(st.session_state.get('query', ''))
    user_input, submitted = render_ui()

    if submitted:
        process_query(user_input)

    if 'travel_info' in st.session_state:
        render_email_form()


if __name__ == '__main__':
    main()