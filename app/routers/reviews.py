from typing import Annotated

from fastapi import APIRouter, Depends, status, HTTPException
from slugify import slugify
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.backend.db_depends import get_db
from app.models.category import Category
from app.models.products import Product
from app.models.reviews import Review
from app.routers.auth import get_current_user
from app.schemas import CreateProduct, CreateReview

router = APIRouter(prefix='/reviews', tags=['reviews'])


@router.get('/')
async def all_reviews(db: Annotated[AsyncSession, Depends(get_db)]):
    reviews = await db.scalars(select(Review).where(Review.is_active == True))
    return reviews.all()


@router.get('/{product_slug}')
async def products_reviews(db: Annotated[AsyncSession, Depends(get_db)], product_slug: str):
    product = await db.scalar(select(Product).where(Product.is_active == True, Product.slug == product_slug))
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Product not found'
        )
    product_reviews = await db.scalars(select(Review).where(Review.is_active == True, Review.product_id == product.id))
    return product_reviews.all()


@router.post('/', status_code=status.HTTP_201_CREATED)
async def add_review(db: Annotated[AsyncSession, Depends(get_db)],
                     create_review: CreateReview,
                     get_user: Annotated[dict, Depends(get_current_user)]):
    if get_user.get('is_customer'):
        product = await db.scalar(select(Product).where(Product.is_active == True, Product.id == create_review.product))
        if product is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Product not found'
            )
        await db.execute(insert(Review).values(
            user_id=get_user.get('id'),
            product_id=create_review.product,
            comment=create_review.comment,
            grade=create_review.grade,
        ))

        reviews = await db.scalars(
            select(Review).where(Review.is_active == True, Review.product_id == create_review.product))
        reviews = reviews.all()
        reviews_len = len(reviews)
        reviews_sum = 0

        for review in reviews:
            reviews_sum += review.grade

        await db.execute(
            update(Product)
            .where(Product.id == create_review.product)
            .values(rating=reviews_sum / reviews_len)
        )
        await db.commit()

        return {
            'status_code': status.HTTP_201_CREATED,
            'transaction': 'Successful'
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='You must be customer user for this'
        )


@router.delete('/{review_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_reviews(db: Annotated[AsyncSession, Depends(get_db)],
                         get_user: Annotated[dict, Depends(get_current_user)], review_id: int):
    review_delete = await db.scalar(select(Review).where(Review.id == review_id))
    if review_delete is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='There is no review found'
        )
    if get_user.get('is_admin'):
        review_delete.is_active = False
        await db.commit()
        return {
            'status_code': status.HTTP_200_OK,
            'transaction': 'Review delete is successful'
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='You have not enough permission for this action'
        )

