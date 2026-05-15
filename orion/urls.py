from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from terminal import views as tv

urlpatterns = [
    path('admin/',    admin.site.urls),
    path('ads.txt',   tv.ads_txt,          name='ads-txt'),

    # Google OAuth
    path('auth/', include('social_django.urls', namespace='social')),

    # Auth
    path('register/', tv.register_view,    name='register'),
    path('login/',    auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/',   tv.logout_view, name='logout'),

    # Pages
    path('',          tv.home_view,        name='home'),
    path('dashboard/', tv.dashboard_view,  name='dashboard'),

    # Setup
    path('api/setup/',                      tv.api_setup,           name='api-setup'),

    # Trades
    path('api/trades/',                     tv.api_trades_list,     name='api-trades'),
    path('api/trades/create/',              tv.api_trades_create,   name='api-trades-create'),
    path('api/trades/forex/',               tv.api_forex_create,    name='api-forex-create'),
    path('api/trades/<int:tid>/',           tv.api_trade_detail,    name='api-trade-detail'),
    path('api/trades/<int:tid>/screenshot/', tv.api_screenshot,     name='api-screenshot'),

    # Reviews
    path('api/reviews/',                    tv.api_reviews,         name='api-reviews'),
    path('api/reviews/<int:tid>/',          tv.api_review_update,   name='api-review-update'),

    # Balance / AI
    path('api/balance/',                    tv.api_balance,         name='api-balance'),
    path('api/ai/',                         tv.api_ai,              name='api-ai'),

    # Brokers & Investors
    path('api/brokers/',                    tv.api_brokers,         name='api-brokers'),
    path('api/brokers/<int:bid>/',          tv.api_broker_detail,   name='api-broker-detail'),
    path('api/investors/',                  tv.api_investors,       name='api-investors'),
    path('api/investors/<int:iid>/',        tv.api_investor_detail, name='api-investor-detail'),

    # Tokens
    path('api/tokens/',                     tv.api_tokens,          name='api-tokens'),

    # Chat
    path('api/chat/',                       tv.api_chat,            name='api-chat'),
    path('api/chat/send/',                  tv.api_chat_send,       name='api-chat-send'),

    # Reset
    path('api/reset/',                      tv.api_reset,           name='api-reset'),
]
