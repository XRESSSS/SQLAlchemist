from asyncpg import UniqueViolationError
from sqlalchemy import insert, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from sqlalchemy.orm import joinedload

from models import User, UserRefreshToken, Product, OrderProduct
from database import async_session_maker
from datetime import datetime


async def create_user(
        name: str,
        email: str,
        hashed_password: str,
        session: AsyncSession,
) -> User:
    user = User(
        email=email,
        name=name,
        hashed_password=hashed_password,
    )
    session.add(user)
    try:
        await session.commit()
        await session.refresh(user)
        return user
    except IntegrityError:
        await session.rollback()
        raise HTTPException(detail=f'User with email {email} probably already exists',
                            status_code=status.HTTP_403_FORBIDDEN)


async def get_user_by_email(email: str, session: AsyncSession) -> User | None:
    query = select(User).filter_by(email=email)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def get_user_by_uuid(user_uuid: str, session: AsyncSession) -> User | None:
    query = select(User).filter_by(user_uuid=user_uuid)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def activate_user_account(user_uuid: str, session: AsyncSession) -> User | None:
    user = await get_user_by_uuid(user_uuid, session)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Data for account activation is not correct"
        )
    if user.verified_at:
        return user

    user.verified_at = True
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def create_refresh_token(
        user_id: int,
        refresh_key: str,
        expires_at: datetime,
        session: AsyncSession,
) -> None:
    token = UserRefreshToken(
        user_id=user_id,
        refresh_key=refresh_key,
        expires_at=expires_at,
    )
    session.add(token)
    await session.commit()


async def get_refresh_token_by_key(key: str, session: AsyncSession) -> UserRefreshToken | None:
    user_token = await session.execute(
        select(UserRefreshToken)
        .options(joinedload(UserRefreshToken.user))
        .where(
            UserRefreshToken.refresh_key == key,
            UserRefreshToken.expires_at > datetime.utcnow(),
        )
    )

    return user_token.scalar_one_or_none()


async def add_product(
        title: str,
        price: float,
        session: AsyncSession,
        image_url: str = '',
        image_file: str = '',
) -> Product | None:
    product = Product(
        title=title,
        price=price,
        image_url=image_url,
        image_file=image_file
    )
    session.add(product)
    try:
        await session.commit()
        await session.refresh(product)
        return product
    except IntegrityError:
        await session.rollback()
        return None


async def fetch_products(session: AsyncSession, offset=0, limit=12, q='') -> list:
    if q:
        query = select(Product).filter(Product.title.ilike(f'%{q}%')).offset(offset).limit(limit)
    else:
        query = select(Product).offset(offset).limit(limit)
    result = await session.execute(query)
    return result.scalars().all() or []


async def get_product(session: AsyncSession, product_id: int) -> Product | None:
    query = select(Product).filter(Product.id == product_id)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def get_or_create(session: AsyncSession, model, only_get=False, **kwargs):
    query = select(model).filter_by(**kwargs)
    instance = await session.execute(query)
    instance = instance.scalar_one_or_none()
    if instance or only_get:
        return instance
    instance = model(**kwargs)
    session.add(instance)
    await session.commit()
    await session.refresh(instance)
    return instance


async def fetch_order_products(session: AsyncSession, order_id: int) -> list:
    query = select(OrderProduct).filter(OrderProduct.order_id == order_id).options(joinedload(OrderProduct.product))
    result = await session.execute(query)
    return result.scalars().all() or []
